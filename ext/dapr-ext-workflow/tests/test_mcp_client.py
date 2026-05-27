# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import json
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import grpc

from dapr.ext.workflow._durabletask import client
from dapr.ext.workflow.aio.mcp import DaprMCPClient as AioDaprMCPClient
from dapr.ext.workflow.mcp import MCP_WORKFLOW_PREFIX, DaprMCPClient, MCPToolDef
from dapr.ext.workflow.workflow_state import WorkflowState


class _StubRpcError(grpc.RpcError):
    """Test double for grpc.RpcError with a configurable status code."""

    def __init__(self, status_code: grpc.StatusCode):
        super().__init__()
        self._status_code = status_code

    def code(self) -> grpc.StatusCode:
        return self._status_code


def _make_completed_state(output_json: dict) -> WorkflowState:
    """Create a WorkflowState that simulates a COMPLETED workflow."""
    inner = client.WorkflowState(
        instance_id='test-id',
        name='test-workflow',
        runtime_status=client.OrchestrationStatus.COMPLETED,
        created_at=datetime.now(),
        last_updated_at=datetime.now(),
        serialized_input=None,
        serialized_output=json.dumps(output_json),
        serialized_custom_status=None,
        failure_details=None,
    )
    return WorkflowState(inner)


def _make_failed_state() -> WorkflowState:
    """Create a WorkflowState that simulates a FAILED workflow."""
    inner = client.WorkflowState(
        instance_id='test-id',
        name='test-workflow',
        runtime_status=client.OrchestrationStatus.FAILED,
        created_at=datetime.now(),
        last_updated_at=datetime.now(),
        serialized_input=None,
        serialized_output='error details',
        serialized_custom_status=None,
        failure_details=None,
    )
    return WorkflowState(inner)


SAMPLE_LIST_TOOLS_RESPONSE = {
    'tools': [
        {
            'name': 'get_weather',
            'description': 'Get current weather for a location.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'location': {'type': 'string', 'description': 'City name'},
                },
                'required': ['location'],
            },
        },
        {
            'name': 'get_forecast',
            'description': 'Get multi-day forecast.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'location': {'type': 'string'},
                    'days': {'type': 'integer'},
                },
                'required': ['location'],
            },
        },
    ]
}


class TestMCPToolDef(unittest.TestCase):
    """Tests for the MCPToolDef dataclass."""

    def test_frozen(self):
        tool = MCPToolDef(
            name='test',
            description='desc',
            input_schema={'type': 'object'},
            server_name='srv',
            call_tool_workflow='dapr.internal.mcp.srv.CallTool',
        )
        with self.assertRaises(AttributeError):
            tool.name = 'changed'

    def test_defaults(self):
        tool = MCPToolDef(name='test', description='desc')
        self.assertEqual(tool.input_schema, {})
        self.assertEqual(tool.server_name, '')
        self.assertEqual(tool.call_tool_workflow, '')


class TestDaprMCPClientConnect(unittest.TestCase):
    """Tests for DaprMCPClient.connect()."""

    def _make_client(self, wf_client: MagicMock) -> DaprMCPClient:
        return DaprMCPClient(timeout_in_seconds=30, wf_client=wf_client)

    def test_connect_schedules_correct_workflow(self):
        """connect() should schedule dapr.internal.mcp.<name>.ListTools."""
        mock_wf = MagicMock()
        mock_wf.schedule_new_workflow.return_value = 'inst-1'
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = self._make_client(mock_wf)
        mcp_client.connect('weather')

        mock_wf.schedule_new_workflow.assert_called_once()
        call_kwargs = mock_wf.schedule_new_workflow.call_args
        self.assertEqual(
            call_kwargs.kwargs['workflow'],
            'dapr.internal.mcp.weather.ListTools',
        )
        self.assertEqual(
            call_kwargs.kwargs['input'],
            {'mcpServerName': 'weather'},
        )

    def test_connect_caches_tools(self):
        """connect() should cache MCPToolDef objects."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = self._make_client(mock_wf)
        mcp_client.connect('weather')

        tools = mcp_client.get_all_tools()
        self.assertEqual(len(tools), 2)
        self.assertIsInstance(tools[0], MCPToolDef)
        self.assertEqual(tools[0].name, 'get_weather')
        self.assertEqual(tools[1].name, 'get_forecast')

    def test_connect_sets_server_name_and_workflow(self):
        """Each MCPToolDef should have server_name and call_tool_workflow set."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = self._make_client(mock_wf)
        mcp_client.connect('weather')

        tool = mcp_client.get_all_tools()[0]
        self.assertEqual(tool.server_name, 'weather')
        self.assertEqual(
            tool.call_tool_workflow,
            'dapr.internal.mcp.weather.CallTool.get_weather',
        )

    def test_connect_preserves_description_and_schema(self):
        """MCPToolDef should carry the original description and inputSchema."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = self._make_client(mock_wf)
        mcp_client.connect('weather')

        tool = mcp_client.get_all_tools()[0]
        self.assertEqual(tool.description, 'Get current weather for a location.')
        self.assertIn('properties', tool.input_schema)

    def test_connect_timeout_raises(self):
        """connect() should raise RuntimeError on timeout (None state)."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = None

        mcp_client = self._make_client(mock_wf)
        with self.assertRaises(RuntimeError) as ctx:
            mcp_client.connect('weather')
        self.assertIn('timed out', str(ctx.exception))

    def test_connect_failed_status_raises(self):
        """connect() should raise RuntimeError on FAILED workflow status."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_failed_state()

        mcp_client = self._make_client(mock_wf)
        with self.assertRaises(RuntimeError) as ctx:
            mcp_client.connect('weather')
        self.assertIn('FAILED', str(ctx.exception))

    def test_connect_empty_tools(self):
        """connect() should handle empty tools list gracefully."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state({'tools': []})

        mcp_client = self._make_client(mock_wf)
        mcp_client.connect('empty-server')

        self.assertEqual(len(mcp_client.get_all_tools()), 0)
        self.assertIn('empty-server', mcp_client.get_connected_servers())


class TestDaprMCPClientFiltering(unittest.TestCase):
    """Tests for allowed_tools filtering."""

    def test_allowed_tools_filters(self):
        """Only tools in allowed_tools should be kept."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = DaprMCPClient(
            allowed_tools={'get_weather'},
            wf_client=mock_wf,
        )
        mcp_client.connect('weather')

        tools = mcp_client.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, 'get_weather')

    def test_allowed_tools_none_keeps_all(self):
        """allowed_tools=None should keep all tools."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = DaprMCPClient(allowed_tools=None, wf_client=mock_wf)
        mcp_client.connect('weather')

        self.assertEqual(len(mcp_client.get_all_tools()), 2)


class TestDaprMCPClientMultiServer(unittest.TestCase):
    """Tests for connecting to multiple MCPServer resources."""

    def test_multiple_servers_accumulate(self):
        """Tools from multiple connect() calls should accumulate."""
        mock_wf = MagicMock()

        weather_response = _make_completed_state(SAMPLE_LIST_TOOLS_RESPONSE)
        local_response = _make_completed_state(
            {
                'tools': [
                    {'name': 'search_files', 'description': 'Search files.'},
                ]
            }
        )
        mock_wf.wait_for_workflow_completion.side_effect = [
            weather_response,
            local_response,
        ]

        mcp_client = DaprMCPClient(wf_client=mock_wf)
        mcp_client.connect('weather')
        mcp_client.connect('local-tools')

        self.assertEqual(len(mcp_client.get_all_tools()), 3)
        self.assertEqual(len(mcp_client.get_server_tools('weather')), 2)
        self.assertEqual(len(mcp_client.get_server_tools('local-tools')), 1)
        self.assertEqual(
            mcp_client.get_connected_servers(),
            ['weather', 'local-tools'],
        )

    def test_get_server_tools_unknown_returns_empty(self):
        """get_server_tools() for unknown server returns empty list."""
        mock_wf = MagicMock()
        mcp_client = DaprMCPClient(wf_client=mock_wf)
        self.assertEqual(mcp_client.get_server_tools('nonexistent'), [])


class TestDaprMCPClientValidation(unittest.TestCase):
    """Tests for input validation."""

    def test_init_zero_timeout_raises(self):
        with self.assertRaises(ValueError):
            DaprMCPClient(timeout_in_seconds=0, wf_client=MagicMock())

    def test_init_negative_timeout_raises(self):
        with self.assertRaises(ValueError):
            DaprMCPClient(timeout_in_seconds=-1, wf_client=MagicMock())

    def test_connect_empty_server_name_raises(self):
        mcp_client = DaprMCPClient(wf_client=MagicMock())
        with self.assertRaises(ValueError):
            mcp_client.connect('')

    def test_connect_whitespace_server_name_raises(self):
        mcp_client = DaprMCPClient(wf_client=MagicMock())
        with self.assertRaises(ValueError):
            mcp_client.connect('   ')

    def test_connect_malformed_json_raises(self):
        """connect() should raise RuntimeError on malformed JSON output."""
        mock_wf = MagicMock()
        inner = client.WorkflowState(
            instance_id='test',
            name='test',
            runtime_status=client.OrchestrationStatus.COMPLETED,
            created_at=datetime.now(),
            last_updated_at=datetime.now(),
            serialized_input=None,
            serialized_output='not valid json{{{',
            serialized_custom_status=None,
            failure_details=None,
        )
        mock_wf.wait_for_workflow_completion.return_value = WorkflowState(inner)

        mcp_client = DaprMCPClient(wf_client=mock_wf)
        with self.assertRaises(RuntimeError) as ctx:
            mcp_client.connect('weather')
        self.assertIn('malformed JSON', str(ctx.exception))

    def test_connect_missing_tool_name_uses_empty_string(self):
        """Tools without a 'name' field should use empty string."""
        mock_wf = MagicMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            {'tools': [{'description': 'No name tool'}]}
        )

        mcp_client = DaprMCPClient(wf_client=mock_wf)
        mcp_client.connect('server')

        tools = mcp_client.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, '')


class TestAioDaprMCPClientConnect(unittest.IsolatedAsyncioTestCase):
    def _make_client(self, wf_client: AsyncMock) -> AioDaprMCPClient:
        return AioDaprMCPClient(timeout_in_seconds=30, wf_client=wf_client)

    async def test_connect_schedules_correct_workflow(self):
        """connect() should schedule dapr.internal.mcp.<name>.ListTools."""
        mock_wf = AsyncMock()
        mock_wf.schedule_new_workflow.return_value = 'inst-1'
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = self._make_client(mock_wf)
        await mcp_client.connect('weather')

        mock_wf.schedule_new_workflow.assert_awaited_once()
        call_kwargs = mock_wf.schedule_new_workflow.call_args
        self.assertEqual(
            call_kwargs.kwargs['workflow'],
            'dapr.internal.mcp.weather.ListTools',
        )
        self.assertEqual(
            call_kwargs.kwargs['input'],
            {'mcpServerName': 'weather'},
        )

    async def test_connect_caches_tools(self):
        """connect() should cache MCPToolDef objects."""
        mock_wf = AsyncMock()
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = self._make_client(mock_wf)
        await mcp_client.connect('weather')

        tools = mcp_client.get_all_tools()
        self.assertEqual(len(tools), 2)
        self.assertIsInstance(tools[0], MCPToolDef)
        self.assertEqual(tools[0].name, 'get_weather')
        self.assertEqual(tools[1].name, 'get_forecast')


class TestDaprMCPClientConnectRetry(unittest.TestCase):
    """Tests for connect()'s retry-on-transient-gRPC-error path."""

    def test_retries_then_succeeds_on_cancelled(self):
        """A CANCELLED schedule failure should be retried within the timeout budget."""
        mock_wf = MagicMock()
        mock_wf.schedule_new_workflow.side_effect = [
            _StubRpcError(grpc.StatusCode.CANCELLED),
            _StubRpcError(grpc.StatusCode.CANCELLED),
            'inst-1',
        ]
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = DaprMCPClient(timeout_in_seconds=30, wf_client=mock_wf)
        with patch('dapr.ext.workflow.mcp.time.sleep'):
            mcp_client.connect('weather')

        self.assertEqual(mock_wf.schedule_new_workflow.call_count, 3)
        self.assertEqual(len(mcp_client.get_all_tools()), 2)

    def test_retries_on_unavailable(self):
        """UNAVAILABLE should also be treated as transient."""
        mock_wf = MagicMock()
        mock_wf.schedule_new_workflow.side_effect = [
            _StubRpcError(grpc.StatusCode.UNAVAILABLE),
            'inst-1',
        ]
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = DaprMCPClient(timeout_in_seconds=30, wf_client=mock_wf)
        with patch('dapr.ext.workflow.mcp.time.sleep'):
            mcp_client.connect('weather')

        self.assertEqual(mock_wf.schedule_new_workflow.call_count, 2)

    def test_non_transient_propagates_immediately(self):
        """A non-CANCELLED/UNAVAILABLE error must not be retried."""
        mock_wf = MagicMock()
        mock_wf.schedule_new_workflow.side_effect = _StubRpcError(
            grpc.StatusCode.PERMISSION_DENIED
        )

        mcp_client = DaprMCPClient(timeout_in_seconds=30, wf_client=mock_wf)
        with patch('dapr.ext.workflow.mcp.time.sleep') as sleep_mock:
            with self.assertRaises(grpc.RpcError):
                mcp_client.connect('weather')

        self.assertEqual(mock_wf.schedule_new_workflow.call_count, 1)
        sleep_mock.assert_not_called()

    def test_deadline_exhausted_raises_last_error(self):
        """When the timeout budget runs out mid-retry, propagate the last error."""
        mock_wf = MagicMock()
        mock_wf.schedule_new_workflow.side_effect = _StubRpcError(
            grpc.StatusCode.CANCELLED
        )

        mcp_client = DaprMCPClient(timeout_in_seconds=1, wf_client=mock_wf)
        # Patch monotonic to advance past the deadline immediately so we don't
        # actually sleep for a second in tests.
        with patch('dapr.ext.workflow.mcp.time.sleep'), patch(
            'dapr.ext.workflow.mcp.time.monotonic',
            side_effect=[0.0, 2.0],
        ):
            with self.assertRaises(grpc.RpcError):
                mcp_client.connect('weather')


class TestAioDaprMCPClientConnectRetry(unittest.IsolatedAsyncioTestCase):
    """Async counterpart of TestDaprMCPClientConnectRetry."""

    async def test_retries_then_succeeds_on_cancelled(self):
        mock_wf = AsyncMock()
        mock_wf.schedule_new_workflow.side_effect = [
            _StubRpcError(grpc.StatusCode.CANCELLED),
            'inst-1',
        ]
        mock_wf.wait_for_workflow_completion.return_value = _make_completed_state(
            SAMPLE_LIST_TOOLS_RESPONSE
        )

        mcp_client = AioDaprMCPClient(timeout_in_seconds=30, wf_client=mock_wf)
        with patch('dapr.ext.workflow.aio.mcp.asyncio.sleep', new=AsyncMock()):
            await mcp_client.connect('weather')

        self.assertEqual(mock_wf.schedule_new_workflow.await_count, 2)
        self.assertEqual(len(mcp_client.get_all_tools()), 2)

    async def test_deadline_exhausted_raises(self):
        mock_wf = AsyncMock()
        mock_wf.schedule_new_workflow.side_effect = _StubRpcError(
            grpc.StatusCode.CANCELLED
        )

        mcp_client = AioDaprMCPClient(timeout_in_seconds=1, wf_client=mock_wf)
        with patch('dapr.ext.workflow.aio.mcp.asyncio.sleep', new=AsyncMock()), patch(
            'dapr.ext.workflow.aio.mcp.time.monotonic',
            side_effect=[0.0, 2.0],
        ):
            with self.assertRaises(grpc.RpcError):
                await mcp_client.connect('weather')


class TestMCPWorkflowPrefix(unittest.TestCase):
    """Tests for the workflow naming constant."""

    def test_prefix_value(self):
        self.assertEqual(MCP_WORKFLOW_PREFIX, 'dapr.internal.mcp.')

    def test_list_tools_name(self):
        name = f'{MCP_WORKFLOW_PREFIX}weather.ListTools'
        self.assertEqual(name, 'dapr.internal.mcp.weather.ListTools')

    def test_call_tool_name(self):
        # CallTool workflows include the tool name as a suffix:
        # dapr.internal.mcp.<server>.CallTool.<tool>
        name = f'{MCP_WORKFLOW_PREFIX}weather.CallTool.get_forecast'
        self.assertEqual(name, 'dapr.internal.mcp.weather.CallTool.get_forecast')


if __name__ == '__main__':
    unittest.main()
