# Dapr Workflow Async Examples (Python)

These examples mirror `examples/workflow/` but author orchestrators with `async def` using the
async workflow APIs. Activities remain regular functions unless noted.

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

Notes:
- Orchestrators use `await ctx.activity(...)`, `await ctx.sleep(...)`, `await ctx.when_all/when_any(...)`, etc.
- No event loop is started manually; the Durable Task worker drives the async orchestrators.
- You can also launch instances using `DaprWorkflowClient` as in the non-async examples.
