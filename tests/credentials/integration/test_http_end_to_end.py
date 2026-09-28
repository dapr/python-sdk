"""DaprHttpClient against a real local HTTPS server."""

import ipaddress
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography import x509

from dapr.clients.health import DaprHealth
from dapr.clients.http.client import DaprHttpClient
from dapr.conf import settings
from dapr.credentials.manager import AsyncCredentialManager
from dapr.credentials.oauth2 import RFC8693TokenExchangeProvider
from dapr.credentials.sources import CallableAttestationSource
from dapr.serializers import DefaultJSONSerializer
from tests.credentials._certs import generate_cert_pair
from tests.credentials.integration._helpers import rotating_token_transport
from tests.credentials.integration.fake_https_server import FakeSecureHttpServer

_LOCALHOST_SAN = [x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]


def _trust_no_verification_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class BearerHeaderReachesTheWireTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        dir_path = Path(self._tmp_dir.name)
        server_cert, server_key = generate_cert_pair(
            common_name='localhost', subject_alt_names=_LOCALHOST_SAN
        )
        cert_path, key_path = dir_path / 'server-cert.pem', dir_path / 'server-key.pem'
        cert_path.write_bytes(server_cert)
        key_path.write_bytes(server_key)

        self.server = FakeSecureHttpServer(
            server_certificate_chain_path=str(cert_path), server_private_key_path=str(key_path)
        )
        self.addCleanup(self.server.stop)

        health_patcher = patch.object(DaprHealth, 'wait_for_sidecar', lambda: None)
        ssl_patcher = patch.object(
            DaprHttpClient, 'get_ssl_context', lambda self: _trust_no_verification_context()
        )
        health_patcher.start()
        ssl_patcher.start()
        self.addCleanup(health_patcher.stop)
        self.addCleanup(ssl_patcher.stop)

    async def test_bearer_header_reaches_the_wire_and_rotates(self):
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            async_transport=rotating_token_transport(),
        )
        manager = AsyncCredentialManager(provider)
        client = DaprHttpClient(DefaultJSONSerializer(), credential_manager=manager)

        await client.send_bytes('GET', f'{self.server.url}/v1.0/metadata', data=None)
        await client.send_bytes('GET', f'{self.server.url}/v1.0/metadata', data=None)

        tokens = [headers['dapr-api-token'] for headers in self.server.received_headers]
        self.assertEqual(len(tokens), 2)
        self.assertNotEqual(tokens[0], tokens[1])

    async def test_bearer_token_replaces_dapr_api_token(self):
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            async_transport=rotating_token_transport(),
        )
        manager = AsyncCredentialManager(provider)
        client = DaprHttpClient(DefaultJSONSerializer(), credential_manager=manager)

        with patch.object(settings, 'DAPR_API_TOKEN', 'static-token'):
            await client.send_bytes('GET', f'{self.server.url}/v1.0/metadata', data=None)

        self.assertEqual(self.server.received_headers[0]['dapr-api-token'], 'token-1')

    async def test_bearer_token_does_not_leak_into_another_clients_requests(self):
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            async_transport=rotating_token_transport(),
        )
        bearer_client = DaprHttpClient(
            DefaultJSONSerializer(), credential_manager=AsyncCredentialManager(provider)
        )
        plain_client = DaprHttpClient(DefaultJSONSerializer())

        await bearer_client.send_bytes('GET', f'{self.server.url}/v1.0/metadata', data=None)
        await plain_client.send_bytes('GET', f'{self.server.url}/v1.0/metadata', data=None)

        self.assertIn('dapr-api-token', self.server.received_headers[0])
        self.assertNotIn('dapr-api-token', self.server.received_headers[1])


if __name__ == '__main__':
    unittest.main()
