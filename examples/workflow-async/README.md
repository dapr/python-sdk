# Dapr Workflow Async Examples (Python)

These examples mirror `examples/workflow/` but author orchestrators with `async def` using the
async workflow APIs. Activities can be either sync or async functions.

## Prerequisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)


How to run:
- Install Dapr CLI: `brew install dapr/tap/dapr-cli` or `choco install dapr-cli`
- Initialize Dapr: `dapr init`
- Install requirements: 
  ```bash
  cd examples/workflow-async
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
  
  or better yet with faster `uv`:
  ```bash
  uv venv .venv
  source .venv/bin/activate
  uv pip install -r requirements.txt
  ```
- Run any example with dapr:
  - `dapr run --app-id wf_async_symple -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python simple.py`
  - `dapr run --app-id wf_task_chain -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python task_chaining.py`
  - `dapr run --app-id wf_async_child -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python child_workflow.py`
  - `dapr run --app-id wf_async_fafi -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python fan_out_fan_in.py`
  - `dapr run --app-id wf_async_gather -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python fan_out_fan_in_with_gather.py`
  - `dapr run --app-id wf_async_approval -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python human_approval.py`
  - `dapr run --app-id wf_ctx_interceptors -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python context_interceptors_example.py`
  - `dapr run --app-id wf_async_http -- /Users/filinto/diagrid/python-sdk/examples/workflow-async/.venv/bin/python async_http_activity.py`

## Examples

- **simple.py**: Comprehensive example showing activities, child workflows, retry policies, and external events
- **task_chaining.py**: Sequential activity calls where each result feeds into the next
- **child_workflow.py**: Parent workflow calling a child workflow
- **fan_out_fan_in.py**: Parallel activity execution pattern
- **fan_out_fan_in_with_gather.py**: Parallel execution using `ctx.when_all()` 
- **human_approval.py**: Workflow waiting for external event to proceed
- **context_interceptors_example.py**: Context propagation using interceptors (tenant, request ID, etc.)
- **async_http_activity.py**: Async activities performing I/O-bound operations (HTTP requests with aiohttp)

Notes:
- Orchestrators use `await ctx.activity(...)`, `await ctx.create_timer(...)`, `await ctx.when_all/when_any(...)`, etc.
- No event loop is started manually; the Durable Task worker drives the async orchestrators.
- You can also launch instances using `DaprWorkflowClient` as in the non-async examples.
- The interceptors example demonstrates how to propagate context (tenant, request ID) across workflow and activity boundaries using the wrapper pattern to avoid contextvar loss.

## Async Activities

Activities can be either synchronous or asynchronous functions. Async activities are useful for I/O-bound operations like HTTP requests, database queries, or file operations:

```python
from dapr.ext.workflow import WorkflowActivityContext

# Synchronous activity
@wfr.activity
def sync_activity(ctx: WorkflowActivityContext, data: str) -> str:
    return data.upper()

# Asynchronous activity
@wfr.activity
async def async_activity(ctx: WorkflowActivityContext, data: str) -> str:
    # Perform async I/O operations
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.example.com/{data}") as response:
            result = await response.json()
    return result
```

Both sync and async activities are registered the same way using the `@wfr.activity` decorator. Orchestrators call them identically regardless of whether they're sync or async - the SDK handles the execution automatically.

**When to use async activities:**
- HTTP requests or API calls
- Database queries
- File I/O operations
- Any I/O-bound work that benefits from async/await

See `async_http_activity.py` for a complete example.
