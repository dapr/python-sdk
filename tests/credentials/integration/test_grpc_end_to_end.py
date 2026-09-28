"""DaprGrpcClient and DaprGrpcClientAsync against a real local gRPC server."""

import asyncio
import unittest
from unittest.mock import patch

import grpc

from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from dapr.clients.grpc.client import DaprGrpcClient
from dapr.clients.health import DaprHealth
from dapr.conf import settings
from dapr.credentials.manager import AsyncCredentialManager, CredentialManager
from dapr.credentials.oauth2 import RFC8693TokenExchangeProvider
from dapr.credentials.sources import CallableAttestationSource
from tests.credentials._certs import generate_cert_pair
from tests.credentials.integration._helpers import rotating_token_transport
from tests.credentials.integration.fake_grpc_server import (
    FakeSecureGrpcServer,
    RecordingDaprServicer,
)


def _patch_health():
    return patch.object(DaprHealth, 'wait_for_sidecar', lambda: None)


class BearerTokenReachesTheWireTests(unittest.TestCase):
    def setUp(self):
        server_cert, server_key = generate_cert_pair(common_name='localhost')
        self.servicer = RecordingDaprServicer()
        self.server = FakeSecureGrpcServer(
            self.servicer, server_certificate_chain=server_cert, server_private_key=server_key
        )
        self.addCleanup(self.server.stop)

        # Bearer channels verify the server via get_credentials(). grpc and grpc.aio can't
        # share a ChannelCredentials object, so each call builds a new one.
        self._patchers = [
            patch.object(
                DaprGrpcClient,
                'get_credentials',
                staticmethod(lambda: grpc.ssl_channel_credentials(server_cert)),
            ),
            patch.object(
                DaprGrpcClientAsync,
                'get_credentials',
                staticmethod(lambda: grpc.ssl_channel_credentials(server_cert)),
            ),
        ]
        for patcher in self._patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _build_provider(self) -> RFC8693TokenExchangeProvider:
        return RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            transport=rotating_token_transport(),
            async_transport=rotating_token_transport(),
        )

    def test_sync_client_sends_and_rotates_bearer_token(self):
        manager = CredentialManager(self._build_provider())
        with _patch_health():
            client = DaprGrpcClient(address=self.server.address, credential_manager=manager)
        self.addCleanup(client.close)

        client.get_metadata()
        client.get_metadata()

        tokens = [dict(m)['dapr-api-token'] for m in self.servicer.received_metadata]
        self.assertEqual(len(tokens), 2)
        self.assertNotEqual(tokens[0], tokens[1])

    async def _async_sends_and_rotates(self):
        manager = AsyncCredentialManager(self._build_provider())
        with _patch_health():
            client = DaprGrpcClientAsync(address=self.server.address, credential_manager=manager)
        try:
            await client.get_metadata()
            await client.get_metadata()
        finally:
            await client.close()

        tokens = [dict(m)['dapr-api-token'] for m in self.servicer.received_metadata]
        self.assertEqual(len(tokens), 2)
        self.assertNotEqual(tokens[0], tokens[1])

    def test_async_client_sends_and_rotates_bearer_token(self):
        asyncio.run(self._async_sends_and_rotates())

    def test_bearer_token_replaces_dapr_api_token(self):
        manager = CredentialManager(self._build_provider())
        with _patch_health(), patch.object(settings, 'DAPR_API_TOKEN', 'static-token'):
            client = DaprGrpcClient(address=self.server.address, credential_manager=manager)
        self.addCleanup(client.close)

        client.get_metadata()

        api_tokens = [v for k, v in self.servicer.received_metadata[0] if k == 'dapr-api-token']
        self.assertEqual(len(api_tokens), 1)
        self.assertTrue(api_tokens[0].startswith('token-'))


if __name__ == '__main__':
    unittest.main()
