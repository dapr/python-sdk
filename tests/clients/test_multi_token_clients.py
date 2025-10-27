# -*- coding: utf-8 -*-

"""
Copyright 2024 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import unittest
from unittest.mock import patch

from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from dapr.clients.grpc.client import DaprGrpcClient
from dapr.clients.health import DaprHealth
from dapr.conf import settings

from .fake_dapr_server import FakeDaprSidecar


class MultiTokenClientTests(unittest.TestCase):
    """Integration tests for multiple clients with different API tokens"""

    grpc_port_1 = 50011
    grpc_port_2 = 50012
    http_port_1 = 3501
    http_port_2 = 3502

    @classmethod
    def setUpClass(cls):
        """Set up two fake Dapr sidecars to simulate different instances"""
        cls._fake_dapr_server_1 = FakeDaprSidecar(
            grpc_port=cls.grpc_port_1, http_port=cls.http_port_1
        )
        cls._fake_dapr_server_2 = FakeDaprSidecar(
            grpc_port=cls.grpc_port_2, http_port=cls.http_port_2
        )
        cls._fake_dapr_server_1.start()
        cls._fake_dapr_server_2.start()

        # Set default HTTP endpoint to first server for health checks
        settings.DAPR_HTTP_PORT = cls.http_port_1
        settings.DAPR_HTTP_ENDPOINT = f'http://127.0.0.1:{cls.http_port_1}'

    @classmethod
    def tearDownClass(cls):
        """Clean up fake servers"""
        cls._fake_dapr_server_1.stop()
        cls._fake_dapr_server_2.stop()

    @patch.object(DaprHealth, 'wait_until_ready')
    def test_multiple_sync_clients_different_tokens(self, mock_health):
        """Test that multiple synchronous clients can use different tokens"""
        # Mock health check to avoid connection issues
        mock_health.return_value = None

        # Create two clients with different tokens
        client1 = DaprGrpcClient(f'localhost:{self.grpc_port_1}', api_token='token-client-1')
        client2 = DaprGrpcClient(f'localhost:{self.grpc_port_2}', api_token='token-client-2')

        try:
            # Make requests with both clients
            resp1 = client1.invoke_method(
                app_id='app1',
                method_name='test',
                data=b'client1',
                content_type='text/plain',
            )

            resp2 = client2.invoke_method(
                app_id='app2',
                method_name='test',
                data=b'client2',
                content_type='text/plain',
            )

            # Verify each client used its own token
            self.assertEqual(b'client1', resp1.data)
            self.assertEqual(['token-client-1'], resp1.headers['hdapr-api-token'])

            self.assertEqual(b'client2', resp2.data)
            self.assertEqual(['token-client-2'], resp2.headers['hdapr-api-token'])

        finally:
            client1.close()
            client2.close()

    @patch.object(DaprHealth, 'wait_until_ready')
    async def test_multiple_async_clients_different_tokens(self, mock_health):
        """Test that multiple async clients can use different tokens"""
        # Mock health check to avoid connection issues
        mock_health.return_value = None

        # Create two async clients with different tokens
        client1 = DaprGrpcClientAsync(f'localhost:{self.grpc_port_1}', api_token='async-token-1')
        client2 = DaprGrpcClientAsync(f'localhost:{self.grpc_port_2}', api_token='async-token-2')

        try:
            # Make requests with both clients
            resp1 = await client1.invoke_method(
                app_id='app1',
                method_name='test',
                data=b'async-client1',
                content_type='text/plain',
            )

            resp2 = await client2.invoke_method(
                app_id='app2',
                method_name='test',
                data=b'async-client2',
                content_type='text/plain',
            )

            # Verify each client used its own token
            self.assertEqual(b'async-client1', resp1.data)
            self.assertEqual(['async-token-1'], resp1.headers['hdapr-api-token'])

            self.assertEqual(b'async-client2', resp2.data)
            self.assertEqual(['async-token-2'], resp2.headers['hdapr-api-token'])

        finally:
            await client1.close()
            await client2.close()

    @patch.object(DaprHealth, 'wait_until_ready')
    @patch.object(settings, 'DAPR_API_TOKEN', 'global-default-token')
    def test_mixing_explicit_and_global_tokens(self, mock_health):
        """Test that clients with explicit tokens coexist with clients using global token"""
        # Mock health check to avoid connection issues
        mock_health.return_value = None

        # Client with explicit token
        client_explicit = DaprGrpcClient(
            f'localhost:{self.grpc_port_1}', api_token='explicit-token'
        )
        # Client using global token
        client_global = DaprGrpcClient(f'localhost:{self.grpc_port_2}')

        try:
            resp_explicit = client_explicit.invoke_method(
                app_id='app1',
                method_name='test',
                data=b'explicit',
                content_type='text/plain',
            )

            resp_global = client_global.invoke_method(
                app_id='app2',
                method_name='test',
                data=b'global',
                content_type='text/plain',
            )

            # Verify explicit token client used its token
            self.assertEqual(b'explicit', resp_explicit.data)
            self.assertEqual(['explicit-token'], resp_explicit.headers['hdapr-api-token'])

            # Verify global token client used the global setting
            self.assertEqual(b'global', resp_global.data)
            self.assertEqual(['global-default-token'], resp_global.headers['hdapr-api-token'])

        finally:
            client_explicit.close()
            client_global.close()

    @patch.object(DaprHealth, 'wait_until_ready')
    def test_client_isolation(self, mock_health):
        """Test that modifying one client's token doesn't affect another"""
        # Mock health check to avoid connection issues
        mock_health.return_value = None

        # Create two clients with different tokens
        client1 = DaprGrpcClient(f'localhost:{self.grpc_port_1}', api_token='isolated-token-1')
        client2 = DaprGrpcClient(f'localhost:{self.grpc_port_2}', api_token='isolated-token-2')

        try:
            # Make a request with client1
            resp1 = client1.invoke_method(
                app_id='app1', method_name='test', data=b'test1', content_type='text/plain'
            )

            # Make a request with client2
            resp2 = client2.invoke_method(
                app_id='app2', method_name='test', data=b'test2', content_type='text/plain'
            )

            # Make another request with client1 to verify it still uses its token
            resp1_again = client1.invoke_method(
                app_id='app1', method_name='test', data=b'test1_again', content_type='text/plain'
            )

            # Verify tokens are isolated
            self.assertEqual(['isolated-token-1'], resp1.headers['hdapr-api-token'])
            self.assertEqual(['isolated-token-2'], resp2.headers['hdapr-api-token'])
            self.assertEqual(['isolated-token-1'], resp1_again.headers['hdapr-api-token'])

        finally:
            client1.close()
            client2.close()

    @patch.object(DaprHealth, 'wait_until_ready')
    @patch.object(settings, 'DAPR_API_TOKEN', None)
    def test_no_token_clients(self, mock_health):
        """Test that clients without tokens work when no global token is set"""
        # Mock health check to avoid connection issues
        mock_health.return_value = None

        client = DaprGrpcClient(f'localhost:{self.grpc_port_1}')

        try:
            resp = client.invoke_method(
                app_id='app1',
                method_name='test',
                data=b'no-token',
                content_type='text/plain',
            )

            # Verify no token was sent
            self.assertNotIn('hdapr-api-token', resp.headers)

        finally:
            client.close()


if __name__ == '__main__':
    unittest.main()
