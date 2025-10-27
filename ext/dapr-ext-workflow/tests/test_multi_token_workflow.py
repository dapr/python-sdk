# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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
from unittest import mock

from dapr.conf import settings
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime


class FakeTaskHubGrpcClient:
    """Fake gRPC client for testing"""

    pass


class FakeTaskHubGrpcWorker:
    """Fake gRPC worker for testing"""

    def add_named_orchestrator(self, name, fn):
        pass

    def add_named_activity(self, name, fn):
        pass


class MultiTokenWorkflowTests(unittest.TestCase):
    """Integration tests for multiple workflow instances with different API tokens"""

    def test_multiple_workflow_clients_different_tokens(self):
        """Test multiple DaprWorkflowClient instances with different tokens"""
        with mock.patch(
            'durabletask.client.TaskHubGrpcClient', return_value=FakeTaskHubGrpcClient()
        ) as mock_grpc_client:
            # Create two clients with different tokens
            _ = DaprWorkflowClient(api_token='token-client-1')
            _ = DaprWorkflowClient(api_token='token-client-2')

            # Verify first client uses its token
            first_call = mock_grpc_client.call_args_list[0]
            metadata1 = first_call[1]['metadata']
            assert len(metadata1) == 1
            assert metadata1[0] == ('dapr-api-token', 'token-client-1')

            # Verify second client uses its token
            second_call = mock_grpc_client.call_args_list[1]
            metadata2 = second_call[1]['metadata']
            assert len(metadata2) == 1
            assert metadata2[0] == ('dapr-api-token', 'token-client-2')

    def test_multiple_workflow_runtimes_different_tokens(self):
        """Test multiple WorkflowRuntime instances with different tokens"""
        with mock.patch(
            'durabletask.worker.TaskHubGrpcWorker', return_value=FakeTaskHubGrpcWorker()
        ) as mock_grpc_worker:
            # Create two runtimes with different tokens
            _ = WorkflowRuntime(api_token='token-runtime-1')
            _ = WorkflowRuntime(api_token='token-runtime-2')

            # Verify first runtime uses its token
            first_call = mock_grpc_worker.call_args_list[0]
            metadata1 = first_call[1]['metadata']
            assert len(metadata1) == 1
            assert metadata1[0] == ('dapr-api-token', 'token-runtime-1')

            # Verify second runtime uses its token
            second_call = mock_grpc_worker.call_args_list[1]
            metadata2 = second_call[1]['metadata']
            assert len(metadata2) == 1
            assert metadata2[0] == ('dapr-api-token', 'token-runtime-2')

    @mock.patch.object(settings, 'DAPR_API_TOKEN', 'global-token')
    def test_mixing_explicit_and_global_tokens(self):
        """Test mixing workflow instances with explicit tokens and global token"""
        with mock.patch(
            'durabletask.client.TaskHubGrpcClient', return_value=FakeTaskHubGrpcClient()
        ) as mock_grpc_client:
            # Client with explicit token
            _ = DaprWorkflowClient(api_token='explicit-token')
            # Client using global token
            _ = DaprWorkflowClient()

            # Verify explicit client uses its token
            first_call = mock_grpc_client.call_args_list[0]
            metadata_explicit = first_call[1]['metadata']
            assert len(metadata_explicit) == 1
            assert metadata_explicit[0] == ('dapr-api-token', 'explicit-token')

            # Verify global client uses global token
            second_call = mock_grpc_client.call_args_list[1]
            metadata_global = second_call[1]['metadata']
            assert len(metadata_global) == 1
            assert metadata_global[0] == ('dapr-api-token', 'global-token')

    def test_client_and_runtime_isolation(self):
        """Test that client and runtime tokens don't interfere with each other"""
        with mock.patch(
            'durabletask.client.TaskHubGrpcClient', return_value=FakeTaskHubGrpcClient()
        ) as mock_client, mock.patch(
            'durabletask.worker.TaskHubGrpcWorker', return_value=FakeTaskHubGrpcWorker()
        ) as mock_worker:
            # Create client and runtime with different tokens
            _ = DaprWorkflowClient(api_token='client-token')
            _ = WorkflowRuntime(api_token='runtime-token')

            # Verify client uses its token
            client_metadata = mock_client.call_args[1]['metadata']
            assert len(client_metadata) == 1
            assert client_metadata[0] == ('dapr-api-token', 'client-token')

            # Verify runtime uses its token
            runtime_metadata = mock_worker.call_args[1]['metadata']
            assert len(runtime_metadata) == 1
            assert runtime_metadata[0] == ('dapr-api-token', 'runtime-token')

    def test_multiple_instances_token_isolation(self):
        """Test that modifying one instance's token doesn't affect another"""
        with mock.patch(
            'durabletask.client.TaskHubGrpcClient', return_value=FakeTaskHubGrpcClient()
        ) as mock_grpc_client:
            # Create three clients with different tokens
            _ = DaprWorkflowClient(api_token='isolated-1')
            _ = DaprWorkflowClient(api_token='isolated-2')
            _ = DaprWorkflowClient(api_token='isolated-3')

            # Verify all three clients use their respective tokens
            calls = mock_grpc_client.call_args_list
            assert len(calls) == 3

            metadata1 = calls[0][1]['metadata']
            assert metadata1[0] == ('dapr-api-token', 'isolated-1')

            metadata2 = calls[1][1]['metadata']
            assert metadata2[0] == ('dapr-api-token', 'isolated-2')

            metadata3 = calls[2][1]['metadata']
            assert metadata3[0] == ('dapr-api-token', 'isolated-3')


if __name__ == '__main__':
    unittest.main()
