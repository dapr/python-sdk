"""DaprClient's HTTP invocation path (DaprInvocationHttpClient) with a credential manager."""

import asyncio
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import grpc

from dapr.clients import DaprClient
from dapr.clients.grpc.client import DaprGrpcClient
from dapr.clients.health import DaprHealth
from dapr.clients.http.client import DaprHttpClient
from dapr.credentials.manager import CredentialManager
from dapr.credentials.oauth2 import RFC8693TokenExchangeProvider
from dapr.credentials.sources import CallableAttestationSource
from tests.credentials._certs import generate_cert_pair
from tests.credentials.integration._helpers import rotating_token_transport
from tests.credentials.integration.fake_https_server import FakeSecureHttpServer


def _trust_none_context(_self) -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _patch_health_and_grpc_credentials():
    """Skips the sidecar health check and restores DaprGrpcClient.get_credentials, which
    tests/clients/test_dapr_grpc_client_secure.py replaces for the rest of the session."""
    return (
        patch.object(DaprHealth, 'wait_for_sidecar', lambda: None),
        patch.object(DaprGrpcClient, 'get_credentials', staticmethod(grpc.ssl_channel_credentials)),
    )


class DaprClientHttpInvocationTests(unittest.TestCase):
    def test_default_http_invocation_client_gets_its_own_manager_over_the_same_provider(self):
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            transport=rotating_token_transport(),
            async_transport=rotating_token_transport(),
        )
        manager = CredentialManager(provider)

        health_patch, credentials_patch = _patch_health_and_grpc_credentials()
        with health_patch, credentials_patch:
            client = DaprClient(address='localhost:1', credential_manager=manager)
        self.addCleanup(client.close)

        self.assertIsNotNone(client.invocation_client)
        http_manager = client.invocation_client._client._credential_manager
        self.assertIsNotNone(http_manager)
        self.assertIsNot(http_manager, manager)
        self.assertIs(http_manager.provider, provider)


class BearerHeaderReachesTheWireViaDaprClientTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        dir_path = Path(self._tmp_dir.name)
        server_cert, server_key = generate_cert_pair(common_name='localhost')
        cert_path, key_path = dir_path / 'cert.pem', dir_path / 'key.pem'
        cert_path.write_bytes(server_cert)
        key_path.write_bytes(server_key)

        self.server = FakeSecureHttpServer(
            server_certificate_chain_path=str(cert_path), server_private_key_path=str(key_path)
        )
        self.addCleanup(self.server.stop)

        ssl_patcher = patch.object(DaprHttpClient, 'get_ssl_context', _trust_none_context)
        ssl_patcher.start()
        self.addCleanup(ssl_patcher.stop)

    def test_invoke_method_over_http_carries_the_bearer_token(self):
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            transport=rotating_token_transport(),
            async_transport=rotating_token_transport(),
        )
        manager = CredentialManager(provider)

        health_patch, credentials_patch = _patch_health_and_grpc_credentials()
        with health_patch, credentials_patch:
            client = DaprClient(address='localhost:1', credential_manager=manager)
        self.addCleanup(client.close)

        # Call the wrapped DaprHttpClient directly so the fake server needn't route invocations.
        underlying_http_client = client.invocation_client._client

        async def call_directly():
            await underlying_http_client.send_bytes(
                'GET', f'{self.server.url}/v1.0/metadata', data=None
            )

        asyncio.run(call_directly())

        tokens = [headers['dapr-api-token'] for headers in self.server.received_headers]
        self.assertEqual(len(tokens), 1)


if __name__ == '__main__':
    unittest.main()
