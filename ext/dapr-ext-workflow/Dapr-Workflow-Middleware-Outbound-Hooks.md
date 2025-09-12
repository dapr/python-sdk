## Dapr Workflow Middleware: Outbound Hooks for Context Propagation

Goal
- Add outbound hooks to Dapr Workflow middleware so adapters can inject tracing/context when scheduling activities/child workflows/signals without wrapping user code.
- Achieve parity with Temporal’s interceptor model: workflow outbound injection + activity inbound restoration.

Why
- Current `RuntimeMiddleware` exposes only inbound lifecycle hooks (workflow/activity start/complete/error). There is no hook before scheduling activities to mutate inputs/headers.
- We currently wrap `ctx.call_activity` to inject tracing. This is effective but adapter-specific and leaks into application flow.

Proposed API
- Extend `dapr.ext.workflow` with additional hook points (illustrative names):

```python
class RuntimeMiddleware(Protocol):
    # existing inbound hooks...
    def on_workflow_start(self, ctx: Any, input: Any): ...
    def on_workflow_complete(self, ctx: Any, result: Any): ...
    def on_workflow_error(self, ctx: Any, error: BaseException): ...
    def on_activity_start(self, ctx: Any, input: Any): ...
    def on_activity_complete(self, ctx: Any, result: Any): ...
    def on_activity_error(self, ctx: Any, error: BaseException): ...

    # new outbound hooks (workflow outbound)
    def on_schedule_activity(
        self,
        ctx: Any,
        activity: Callable[..., Any] | str,
        input: Any,
        retry_policy: Any | None,
    ) -> Any:  # returns possibly-modified input
        """Called just before scheduling an activity. Return new input to use."""

    def on_start_child_workflow(
        self,
        ctx: Any,
        workflow: Callable[..., Any] | str,
        input: Any,
    ) -> Any:  # returns possibly-modified input
        """Called before starting a child workflow."""

    def on_signal_workflow(
        self,
        ctx: Any,
        signal_name: str,
        input: Any,
    ) -> Any:  # returns possibly-modified input
        """Called before signaling a workflow."""
```

Behavior
- Hooks run within workflow sandbox; must be deterministic and side-effect free.
- The engine uses the middleware’s return value as the actual input for the scheduling call.
- If multiple middlewares are installed, chain them in order (each sees the previous result).
- If a hook raises, log and continue with the last good value (non-fatal by default).

Reference Impl (engine changes)
- In the workflow context implementation, just before delegating to DurableTask’s schedule API:
  - Call `on_schedule_activity(ctx, activity, input, retry_policy)` for each installed middleware.
  - Use the returned input for the actual schedule call.
  - Repeat pattern for child workflows and signals.

Adapter usage (example)
```python
class TraceContextMiddleware(RuntimeMiddleware):
    def on_schedule_activity(self, ctx, activity, input, retry_policy):
        from agents_sdk.adapters.openai.tracing import serialize_trace_context
        tracing = serialize_trace_context()
        if input is None:
            return {"tracing": tracing}
        if isinstance(input, dict) and "tracing" not in input:
            return {**input, "tracing": tracing}
        return input

    # inbound restore already implemented via on_activity_start/complete/error
```

Determinism Constraints
- No non-deterministic APIs (time, random, network) inside hooks.
- Pure data transformation of provided `input` + current context-derived data already in scope.
- If adapters need time/ids, they must obtain deterministic values from the workflow context (e.g., `ctx.current_utc_datetime`).

Error Handling Policy
- Hook exceptions are caught and logged; scheduling proceeds with the last known value.
- Optionally, add a strict mode flag at runtime init to fail-fast on hook errors.

Testing Plan
- Unit
  - on_schedule_activity merges tracing into None and dict inputs; leaves non-dict unchanged.
  - Chaining: two middlewares both modify input; verify order and final payload.
  - Exceptions: first middleware raises, second still runs; input falls back correctly.
- Integration (workflow sandbox)
  - Workflow calls multiple activities; verify each receives tracing in input.
  - Mixed: activity + sleep + when_all; ensure only activities are modified.
  - Child workflow path: verify `on_start_child_workflow` injects tracing.
  - Signal path: verify `on_signal_workflow` injects tracing payload.
- Determinism
  - Re-run workflow with same history: identical decisions and payloads.
  - Ensure no network/time/random usage in hooks; static analysis/lint rules.

Migration for this repo
- Once the SDK exposes outbound hooks:
  - Remove `wrap_ctx_inject_tracing` and `activity_restore_wrapper` from the adapter wiring.
  - Keep inbound restoration in middleware only (already implemented).
  - Simplify `AgentWorkflowRuntime` so it doesn’t need context wrappers.

Open Questions
- Should hooks support header/metadata objects in addition to input payload mutation?
- Do we need an outbound hook for external events (emit) beyond signals?

Timeline
- Week 1: Implement engine hooks + unit tests in SDK.
- Week 2: Add integration tests; update docs and examples.
- Week 3: Migrate adapters here to middleware-only; delete wrappers.


