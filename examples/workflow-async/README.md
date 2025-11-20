# Dapr Workflow Async Examples (Python)

These examples mirror `examples/workflow/` but author orchestrators with `async def` using the
async workflow APIs. Activities remain regular functions unless noted.

How to run:
- Ensure a Dapr sidecar is running locally. If needed, set `DURABLETASK_GRPC_ENDPOINT`, or
  `DURABLETASK_GRPC_HOST/PORT`.
- Install requirements: `pip install -r requirements.txt`
- Run any example: `python simple.py`

Notes:
- Orchestrators use `await ctx.activity(...)`, `await ctx.sleep(...)`, `await ctx.when_all/when_any(...)`, etc.
- No event loop is started manually; the Durable Task worker drives the async orchestrators.
- You can also launch instances using `DaprWorkflowClient` as in the non-async examples.
