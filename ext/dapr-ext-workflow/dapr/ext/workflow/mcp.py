# -*- coding: utf-8 -*-

# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
DaprMCPClient — framework-agnostic client for discovering and cataloguing
MCP tools exposed by Dapr MCPServer resources.

The client schedules Dapr's built-in workflow orchestrations
(``dapr.internal.mcp.<server>.ListTools`` / ``CallTool``) and returns
plain :class:`MCPToolDef` dataclasses that any agent framework can consume.

Usage::

    from dapr.ext.workflow import DaprMCPClient

    client = DaprMCPClient()
    client.connect("weather")
    for tool in client.get_all_tools():
        print(tool.name, tool.description)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient
from dapr.ext.workflow.workflow_state import WorkflowStatus

logger = logging.getLogger(__name__)

# MCP workflow name constants — mirrors the proto enums in
# dapr/dapr/dapr/proto/workflows/v1/mcp.proto as plain strings.
MCP_WORKFLOW_PREFIX: str = 'dapr.internal.mcp.'
"""Prefix for all built-in MCP workflow orchestrations."""

_MCP_METHOD_LIST_TOOLS = '.ListTools'
_MCP_METHOD_CALL_TOOL = '.CallTool'


# TODO(@sicoyle): see if I can use the mcp pkg class instead for this?
@dataclass(frozen=True)
class MCPToolDef:
    """Framework-agnostic description of a single MCP tool.

    Returned by :meth:`DaprMCPClient.get_all_tools` and consumed by
    agent frameworks to build their own tool wrappers.

    Attributes:
        name: The MCP tool name as returned by the server (e.g. ``get_weather``).
        description: Human-readable description of what the tool does.
        input_schema: JSON Schema dict describing the tool's input parameters.
        server_name: Name of the Dapr ``MCPServer`` resource that hosts this tool.
        call_tool_workflow: Pre-computed workflow name for invoking this tool
            (e.g. ``dapr.internal.mcp.weather.CallTool.get_weather``).
    """

    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ''
    call_tool_workflow: str = ''


class _DaprMCPClientBase:
    """Shared state and getters for sync/async MCP clients."""

    def __init__(
        self,
        *,
        timeout_in_seconds: int = 60,
        allowed_tools: Optional[Set[str]] = None,
    ) -> None:
        if timeout_in_seconds <= 0:
            raise ValueError('timeout_in_seconds must be a positive integer')
        self._timeout = timeout_in_seconds
        self._allowed_tools = allowed_tools
        self._server_tools: Dict[str, List[MCPToolDef]] = {}

    def _process_list_tools_result(
        self, mcpserver_name: str, serialized_output: Optional[str]
    ) -> None:
        """Parse a ListTools workflow output and cache the MCPToolDef list."""
        try:
            result = json.loads(serialized_output) if serialized_output else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"ListTools workflow for MCPServer '{mcpserver_name}' returned "
                f'malformed JSON: {exc}'
            ) from exc

        tools: List[MCPToolDef] = []
        for tool_def in result.get('tools', []):
            name = tool_def.get('name', '')
            if self._allowed_tools is not None and name not in self._allowed_tools:
                logger.debug("Skipping tool '%s' (not in allowed_tools)", name)
                continue
            # Workflow name includes the tool name for per-tool observability:
            # dapr.internal.mcp.<server>.CallTool.<tool>
            call_tool_wf = f'{MCP_WORKFLOW_PREFIX}{mcpserver_name}{_MCP_METHOD_CALL_TOOL}.{name}'
            tools.append(
                MCPToolDef(
                    name=name,
                    description=tool_def.get('description', ''),
                    input_schema=tool_def.get('inputSchema') or {},
                    server_name=mcpserver_name,
                    call_tool_workflow=call_tool_wf,
                )
            )

        self._server_tools[mcpserver_name] = tools
        logger.info(
            "Connected to MCPServer '%s': %d tool(s) loaded",
            mcpserver_name,
            len(tools),
        )

    def get_all_tools(self) -> List[MCPToolDef]:
        """Return all cached tools from every connected MCPServer."""
        return [t for tools in self._server_tools.values() for t in tools]

    def get_server_tools(self, server_name: str) -> List[MCPToolDef]:
        """Return cached tools for a specific MCPServer."""
        return list(self._server_tools.get(server_name, []))

    def get_connected_servers(self) -> List[str]:
        """Return the names of all MCPServers connected so far."""
        return list(self._server_tools.keys())


class DaprMCPClient(_DaprMCPClientBase):
    """Framework-agnostic client for discovering MCP tools via Dapr workflows.

    This client schedules Dapr's built-in workflow orchestrations
    (``ListTools`` / ``CallTool``) via :class:`DaprWorkflowClient`.
    It returns :class:`MCPToolDef` dataclasses — plain data objects
    with no framework dependencies — that any agent framework can convert
    to its own tool type.

    Args:
        timeout_in_seconds: Maximum seconds to wait for each ``ListTools``
            workflow to complete.  Defaults to 60.
        allowed_tools: Optional set of tool names to keep.  When provided,
            only tools whose name appears in this set are included in the
            catalogue.  ``None`` (default) keeps all tools.
        wf_client: Optional pre-configured :class:`DaprWorkflowClient`.
            If omitted, a new client is created with default settings.

    Example::

        client = DaprMCPClient()
        client.connect("weather")
        tools = client.get_all_tools()   # List[MCPToolDef]

        # Each framework converts MCPToolDef to its own tool type:
        for t in tools:
            print(f"{t.name}: {t.call_tool_workflow}")
    """

    def __init__(
        self,
        *,
        timeout_in_seconds: int = 60,
        allowed_tools: Optional[Set[str]] = None,
        wf_client: Optional[DaprWorkflowClient] = None,
    ) -> None:
        super().__init__(
            timeout_in_seconds=timeout_in_seconds,
            allowed_tools=allowed_tools,
        )
        self._wf_client = wf_client or DaprWorkflowClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self, mcpserver_name: str) -> None:
        """Discover tools from a Dapr MCPServer resource.

        Schedules ``dapr.internal.mcp.<name>.ListTools``, blocks until the
        workflow completes, and caches the resulting :class:`MCPToolDef` list.

        Args:
            mcpserver_name: Name of the ``MCPServer`` Dapr resource (must
                match the ``metadata.name`` in the MCPServer YAML).

        Raises:
            RuntimeError: If the workflow times out or ends with a non-COMPLETED
                status.
        """
        if not mcpserver_name or not mcpserver_name.strip():
            raise ValueError('mcpserver_name must be a non-empty string')

        instance_id = str(uuid.uuid4())
        # TODO(@sicoyle): reminder to add a func like I have in durabletask-go to use for here instead of building like this!
        workflow_name = f'{MCP_WORKFLOW_PREFIX}{mcpserver_name}{_MCP_METHOD_LIST_TOOLS}'

        logger.debug('Scheduling %s (instance=%s)', workflow_name, instance_id)

        self._wf_client.schedule_new_workflow(
            workflow=workflow_name,
            input={'mcpServerName': mcpserver_name},
            instance_id=instance_id,
        )

        state = self._wf_client.wait_for_workflow_completion(
            instance_id=instance_id,
            timeout_in_seconds=self._timeout,
            fetch_payloads=True,
        )

        if state is None:
            raise RuntimeError(
                f"ListTools workflow for MCPServer '{mcpserver_name}' "
                f'timed out after {self._timeout}s'
            )

        if state.runtime_status != WorkflowStatus.COMPLETED:
            raise RuntimeError(
                f"ListTools workflow for MCPServer '{mcpserver_name}' "
                f'ended with status {state.runtime_status.name!r}: '
                f'{state.serialized_output or ""}'
            )

        self._process_list_tools_result(mcpserver_name, state.serialized_output)
