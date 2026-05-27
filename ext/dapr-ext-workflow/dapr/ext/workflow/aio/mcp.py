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

"""Async variant of :class:`~dapr.ext.workflow.mcp.DaprMCPClient`."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional, Set

from dapr.ext.workflow.aio.dapr_workflow_client import DaprWorkflowClient
from dapr.ext.workflow.mcp import (
    _MCP_METHOD_LIST_TOOLS,
    _SCHEDULE_RETRY_INTERVAL_SECONDS,
    MCP_WORKFLOW_PREFIX,
    _DaprMCPClientBase,
    _is_transient_schedule_error,
)
from dapr.ext.workflow.workflow_state import WorkflowStatus

logger = logging.getLogger(__name__)


class DaprMCPClient(_DaprMCPClientBase):
    """Async framework-agnostic client for discovering MCP tools via Dapr workflows.

    This is the async counterpart of :class:`dapr.ext.workflow.mcp.DaprMCPClient`.
    All methods that interact with the Dapr sidecar are ``async``.

    Args:
        timeout_in_seconds: Maximum seconds to wait for each ``ListTools``
            workflow to complete.
        allowed_tools: Optional set of tool names to keep.
        wf_client: Optional pre-configured async :class:`DaprWorkflowClient`.

    Example::

        from dapr.ext.workflow.aio import DaprMCPClient

        client = DaprMCPClient()
        await client.connect("weather")
        tools = client.get_all_tools()
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

    async def connect(self, mcpserver_name: str) -> None:
        """Discover tools from a Dapr MCPServer resource.

        Schedules ``dapr.internal.mcp.<name>.ListTools``, awaits workflow
        completion, and caches the resulting :class:`MCPToolDef` list.

        Args:
            mcpserver_name: Name of the ``MCPServer`` Dapr resource (must
                match the ``metadata.name`` in the MCPServer YAML).

        Raises:
            RuntimeError: If the workflow times out or ends with a non-COMPLETED
                status.
            ValueError: If *mcpserver_name* is empty.
        """
        if not mcpserver_name or not mcpserver_name.strip():
            raise ValueError('mcpserver_name must be a non-empty string')

        instance_id = str(uuid.uuid4())
        # TODO(@sicoyle): reminder to add a func like I have in durabletask-go to use for here instead of building like this!
        workflow_name = f'{MCP_WORKFLOW_PREFIX}{mcpserver_name}{_MCP_METHOD_LIST_TOOLS}'

        logger.debug('Scheduling %s (instance=%s)', workflow_name, instance_id)

        deadline = time.monotonic() + self._timeout
        while True:
            try:
                await self._wf_client.schedule_new_workflow(
                    workflow=workflow_name,
                    input={'mcpServerName': mcpserver_name},
                    instance_id=instance_id,
                )
                break
            except Exception as exc:  # noqa: BLE001 — classified by helper
                if not _is_transient_schedule_error(exc):
                    raise
                sleep_for = min(_SCHEDULE_RETRY_INTERVAL_SECONDS, deadline - time.monotonic())
                if sleep_for <= 0:
                    raise
                logger.debug('schedule_new_workflow returned transient error %s; retrying', exc)
                await asyncio.sleep(sleep_for)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"ListTools workflow for MCPServer '{mcpserver_name}' "
                f'timed out after {self._timeout}s'
            )
        # wait_for_workflow_completion treats timeout=0 as "wait forever",
        # so floor the gRPC timeout at 1s when sub-second remaining survives.
        state = await self._wf_client.wait_for_workflow_completion(
            instance_id=instance_id,
            timeout_in_seconds=max(int(remaining), 1),
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
