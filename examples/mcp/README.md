# MCP Examples

Examples demonstrating how to use the `DaprMCPClient` from the Dapr Python SDK
to discover and invoke MCP tools via Dapr's built-in workflow orchestrations.

## Prerequisites

- **Dapr CLI** installed with `dapr init` completed (provides Redis on `localhost:6379`)
- **Python 3.11+**
- Install deps: `pip install -r requirements.txt`

## Files

| File | Purpose |
|------|---------|
| `mcp_tool_discovery.py` | The example: discovers tools and runs one in a workflow. |
| `weather_mcp_server.py` | Self-contained MCP server with `get_weather` / `get_forecast` tools (streamable-HTTP on `:8081/mcp`). |
| `resources/weather.yaml` | Dapr `MCPServer` resource pointing the sidecar at the weather server. |
| `resources/statestore.yaml` | Redis state store with `actorStateStore: true` (required by workflows). |

## Run

In one terminal, start the bundled MCP server:

```bash
python weather_mcp_server.py
```

In another terminal, run the example with Dapr:

```bash
dapr run \
  --app-id mcp-demo \
  --resources-path ./resources \
  -- python mcp_tool_discovery.py
```

The example will:

1. Connect to the `weather` MCPServer resource via the sidecar.
2. Print each discovered tool's name, description, and workflow name.
3. Schedule a `CallTool` child workflow for the first tool with `{"location": "Seattle"}`.
4. Print the result.

## Using a different MCP server

Edit `resources/weather.yaml` to point at any MCP-compatible endpoint. Supported
transports:

```yaml
spec:
  endpoint:
    streamableHTTP:
      url: http://host:port/mcp
```

```yaml
spec:
  endpoint:
    sse:
      url: http://host:port/sse
```

```yaml
spec:
  endpoint:
    stdio:
      command: python
      args: ["path/to/server.py"]
```

## `DaprMCPClient` API at a glance

`DaprMCPClient` is **framework-agnostic**: it returns plain `MCPToolDef` dataclasses, not framework-specific tool wrappers. This lets the same client power dapr-agents, LangChain, AutoGen, or any hand-rolled agent loop.

```python
from dapr.ext.workflow import DaprMCPClient

client = DaprMCPClient(timeout_in_seconds=30, allowed_tools={"get_weather"})
client.connect("weather")

for tool in client.get_all_tools():
    print(tool.name, "→", tool.call_tool_workflow)
```

`MCPToolDef` carries:

- `name` — MCP tool name (e.g., `"get_weather"`).
- `description` — human-readable description.
- `input_schema` — JSON Schema for the tool's arguments.
- `server_name` — the `MCPServer` resource the tool came from.
- `call_tool_workflow` — the pre-computed `dapr.internal.mcp.<server>.CallTool.<tool>` workflow name.

Public methods: `connect(name)`, `get_all_tools()`, `get_server_tools(name)`, `get_connected_servers()`. The async equivalent lives at `dapr.ext.workflow.aio.DaprMCPClient`.

## Wiring `MCPToolDef` into a non-dapr-agents framework

`MCPToolDef` is intentionally framework-agnostic — you need a small translation step to convert it into your framework's tool type. The translation binds two things:

1. The tool's `call_tool_workflow` name into a callable that schedules it as a child workflow (passing `{"arguments": kwargs}` as input).
2. The `input_schema` into whatever args validator your framework uses (Pydantic, JSON Schema validator, etc.).

dapr-agents ships such a helper out of the box; for other frameworks the shim is typically under 30 lines. Sketch:

```python
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from dapr.ext.workflow import DaprMCPClient

# ---- 1. Discover ---------------------------------------------------------
client = DaprMCPClient()
client.connect("weather")

# ---- 2. Translate each MCPToolDef into your framework's tool ------------
def to_my_framework_tool(tool_def):
    # Build an args model from the JSON Schema
    args_model: Optional[Type[BaseModel]] = build_pydantic_model(
        tool_def.input_schema, f"{tool_def.name}Args"
    )

    # Build the executor that schedules the child workflow
    def _executor(ctx: Any, **kwargs: Any) -> Any:
        return ctx.call_child_workflow(
            workflow=tool_def.call_tool_workflow,
            input={"arguments": kwargs},
        )

    return MyFrameworkTool(
        name=tool_def.name,
        description=tool_def.description,
        func=_executor,
        args_model=args_model,
    )

tools = [to_my_framework_tool(t) for t in client.get_all_tools()]
# ... pass `tools` to your framework's agent constructor.
```

If you're using **dapr-agents**, you don't write this yourself — `DurableAgent` auto-discovers MCPServer resources from the sidecar and wires them up. See the dapr-agents docs for details.
