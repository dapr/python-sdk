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
MCP Tool Discovery Example
===========================

Demonstrates using DaprMCPClient to discover MCP tools from Dapr
MCPServer resources — without any agent framework dependency.

This is the SDK-level client that any agent framework can build on top of.

Prerequisites
-------------
1. A Dapr MCPServer resource named "weather" loaded in the sidecar::

       apiVersion: dapr.io/v1alpha1
       kind: MCPServer
       metadata:
         name: weather
       spec:
         endpoint:
           streamableHTTP:
             url: http://localhost:8081/mcp

2. An MCP server running at the configured URL.

Run
---
::

    dapr run --app-id mcp-demo --resources-path ./resources -- python mcp_tool_discovery.py
"""

from dapr.ext.workflow import (
    DaprMCPClient,
    DaprWorkflowClient,
    DaprWorkflowContext,
    WorkflowActivityContext,
    WorkflowRuntime,
)
from dapr.ext.workflow.mcp_schema import create_pydantic_model_from_schema


def call_mcp_tool_workflow(ctx: DaprWorkflowContext, input: dict):
    """Workflow that calls an MCP tool as a child workflow.

    Input dict shape::

        {
            "call_tool_workflow": "<dapr.internal.mcp.<server>.CallTool>",
            "tool_name": "<tool name>",
            "arguments": { ... },
        }
    """
    result = yield ctx.call_child_workflow(
        workflow=input['call_tool_workflow'],
        input={
            'toolName': input['tool_name'],
            'arguments': input.get('arguments', {}),
        },
    )
    return result


def print_result(ctx: WorkflowActivityContext, input):
    """Activity that prints the tool result."""
    print(f'  Tool result: {input}')


def main():
    # ------------------------------------------------------------------
    # 1. Discover MCP tools from a Dapr MCPServer resource.
    # ------------------------------------------------------------------
    print("Connecting to MCPServer 'weather'...")

    client = DaprMCPClient(timeout_in_seconds=30)
    client.connect('weather')

    tools = client.get_all_tools()
    print(f'\nDiscovered {len(tools)} tool(s):\n')
    for tool in tools:
        print(f'  Name:        {tool.name}')
        print(f'  Description: {tool.description}')
        print(f'  Server:      {tool.server_name}')
        print(f'  Workflow:    {tool.call_tool_workflow}')
        if tool.input_schema.get('properties'):
            props = list(tool.input_schema['properties'].keys())
            print(f'  Parameters:  {", ".join(props)}')
        print()

    # ------------------------------------------------------------------
    # 2. Use the tool in a Dapr workflow.
    #    This shows how any framework can use MCPToolDef to schedule
    #    durable tool calls via child workflows.
    # ------------------------------------------------------------------
    if not tools:
        print('No tools discovered — exiting.')
        return

    tool = tools[0]
    print(f"Using tool '{tool.name}' in a workflow...\n")

    # Build a Pydantic model from the tool's JSON Schema for validation.
    if tool.input_schema:
        ArgsModel = create_pydantic_model_from_schema(tool.input_schema, f'{tool.name}Args')
        print(f'  Args model: {ArgsModel.__name__}')
        print(f'  Fields:     {list(ArgsModel.model_fields.keys())}\n')

    # Register and run the workflow.
    wfr = WorkflowRuntime()
    wfr.register_workflow(call_mcp_tool_workflow)
    wfr.register_activity(print_result)
    wfr.start()

    wf_client = DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(
        workflow=call_mcp_tool_workflow,
        input={
            'call_tool_workflow': tool.call_tool_workflow,
            'tool_name': tool.name,
            'arguments': {'location': 'Seattle'},
        },
    )
    print(f'  Scheduled workflow: {instance_id}')

    state = wf_client.wait_for_workflow_completion(
        instance_id=instance_id,
        timeout_in_seconds=30,
        fetch_payloads=True,
    )

    if state:
        print(f'  Status: {state.runtime_status.name}')
        print(f'  Output: {state.serialized_output}')
    else:
        print('  Workflow timed out.')

    wfr.shutdown()
    print('\nDone.')


if __name__ == '__main__':
    main()
