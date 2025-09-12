dapr-ext-workflow extension
===========================

|pypi|

.. |pypi| image:: https://badge.fury.io/py/dapr-ext-workflow.svg
   :target: https://pypi.org/project/dapr-ext-workflow/

This is the workflow authoring extension for Dapr Workflow


Installation
------------

::

    pip install dapr-ext-workflow

Async authoring (experimental)
------------------------------

This package supports authoring workflows with ``async def`` in addition to the existing generator-based orchestrators.

- Register async workflows using ``WorkflowRuntime.workflow`` (auto-detects coroutine) or ``async_workflow`` / ``register_async_workflow``.
- Use ``AsyncWorkflowContext`` for deterministic operations:

  - Activities: ``await ctx.call_activity(activity_fn, input=...)``
  - Child workflows: ``await ctx.call_child_workflow(workflow_fn, input=...)``
  - Timers: ``await ctx.create_timer(seconds|timedelta)``
  - External events: ``await ctx.wait_for_external_event(name)``
  - Concurrency: ``await ctx.when_all([...])``, ``await ctx.when_any([...])``
  - Deterministic utils: ``ctx.now()``, ``ctx.random()``, ``ctx.uuid4()``

Interceptors (client/runtime/outbound)
--------------------------------------

Interceptors provide a simple, composable way to apply cross-cutting behavior with a single
enter/exit per call. There are three types:

- Client interceptors: wrap outbound scheduling from the client (schedule_new_workflow).
- Workflow outbound interceptors: wrap calls made inside workflows (call_activity, call_child_workflow).
- Runtime interceptors: wrap inbound execution of workflows and activities (before user code).

Use cases include context propagation, request metadata stamping, replay-aware logging, validation,
and policy enforcement.

Quick start
~~~~~~~~~~~

.. code-block:: python

    from __future__ import annotations
    import contextvars
    from typing import Any, Callable

    from dapr.ext.workflow import (
        WorkflowRuntime,
        DaprWorkflowClient,
        ClientInterceptor,
        WorkflowOutboundInterceptor,
        RuntimeInterceptor,
        ScheduleWorkflowInput,
        CallActivityInput,
        CallChildWorkflowInput,
        ExecuteWorkflowInput,
        ExecuteActivityInput,
    )

    # Example: propagate a lightweight context dict through inputs
    _current_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
        'wf_ctx', default=None
    )

    def set_ctx(ctx: dict[str, Any] | None):
        _current_ctx.set(ctx)

    def _merge_ctx(args: Any) -> Any:
        ctx = _current_ctx.get()
        if ctx and isinstance(args, dict) and 'context' not in args:
            return {**args, 'context': ctx}
        return args

    class ContextClientInterceptor(ClientInterceptor):
        def schedule_new_workflow(self, input: ScheduleWorkflowInput, nxt: Callable[[ScheduleWorkflowInput], Any]) -> Any:
            input = ScheduleWorkflowInput(
                workflow_name=input.workflow_name,
                args=_merge_ctx(input.args),
                instance_id=input.instance_id,
                start_at=input.start_at,
                reuse_id_policy=input.reuse_id_policy,
            )
            return nxt(input)

    class ContextWorkflowOutboundInterceptor(WorkflowOutboundInterceptor):
        def call_child_workflow(self, input: CallChildWorkflowInput, nxt: Callable[[CallChildWorkflowInput], Any]) -> Any:
            return nxt(CallChildWorkflowInput(
                workflow_name=input.workflow_name,
                args=_merge_ctx(input.args),
                instance_id=input.instance_id,
                workflow_ctx=input.workflow_ctx,
                metadata=input.metadata,
                local_context=input.local_context,
            ))

        def call_activity(self, input: CallActivityInput, nxt: Callable[[CallActivityInput], Any]) -> Any:
            return nxt(CallActivityInput(
                activity_name=input.activity_name,
                args=_merge_ctx(input.args),
                retry_policy=input.retry_policy,
                workflow_ctx=input.workflow_ctx,
                metadata=input.metadata,
                local_context=input.local_context,
            ))

    class ContextRuntimeInterceptor(RuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, nxt: Callable[[ExecuteWorkflowInput], Any]) -> Any:
            # Restore context from input if present (no I/O, replay-safe)
            if isinstance(input.input, dict) and 'context' in input.input:
                set_ctx(input.input['context'])
            try:
                return nxt(input)
            finally:
                set_ctx(None)

        def execute_activity(self, input: ExecuteActivityInput, nxt: Callable[[ExecuteActivityInput], Any]) -> Any:
            if isinstance(input.input, dict) and 'context' in input.input:
                set_ctx(input.input['context'])
            try:
                return nxt(input)
            finally:
                set_ctx(None)

    # Wire into client and runtime
    runtime = WorkflowRuntime(
        runtime_interceptors=[ContextRuntimeInterceptor()],
        workflow_outbound_interceptors=[ContextWorkflowOutboundInterceptor()],
    )

    client = DaprWorkflowClient(interceptors=[ContextClientInterceptor()])

Context metadata and local_context (durable propagation)
-------------------------------------------------------

Interceptors support two extra context channels:

- ``metadata``: a string-only dict that is durably persisted and propagated across workflow
  boundaries (schedule, child workflows, activities). Typical use: tracing and correlation ids
  (e.g., ``otel.trace_id``), tenancy, request ids. This is provider-agnostic and does not require
  changes to your workflow/activities.
- ``local_context``: an in-process dict for non-serializable objects (e.g., bound loggers, tracing
  span objects, redaction policies). It is not persisted and does not cross process boundaries.

How it works
~~~~~~~~~~~~

- Client interceptors can set ``metadata`` when scheduling a workflow or calling activities/children.
- Runtime unwraps a reserved envelope before user code runs and exposes the metadata to
  ``RuntimeInterceptor`` via ``ExecuteWorkflowInput.metadata`` / ``ExecuteActivityInput.metadata``,
  while delivering only the original payload to the user function.
- Outbound calls made inside a workflow use client interceptors; when ``metadata`` is present on the
  call input, the runtime re-wraps the payload to persist and propagate it.

Envelope (backward compatible)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Internally, the runtime persists metadata by wrapping inputs in an envelope:

::

    {
      "__dapr_meta__": { "v": 1, "metadata": { "otel.trace_id": "abc" } },
      "__dapr_payload__": { ... original user input ... }
    }

- The runtime unwraps this automatically so user code continues to receive the exact original input
  structure and types.
- The version field (``v``) is reserved for forward compatibility.

Determinism and safety
~~~~~~~~~~~~~~~~~~~~~~

- In workflows, read metadata and avoid non-deterministic operations inside interceptors. Do not
  perform network I/O in orchestrators.
- Activities may read/modify metadata and perform I/O inside the activity function if desired.
- Keep ``local_context`` for in-process state only; mirror string identifiers to ``metadata`` if you
  need propagation across activities/children.

Tracing interceptors (example)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can implement tracing as interceptors that stamp/propagate IDs in ``metadata`` and suppress
spans during replay. A minimal sketch:

.. code-block:: python

    from typing import Any, Callable
    from dapr.ext.workflow import (
        BaseClientInterceptor, BaseWorkflowOutboundInterceptor, BaseRuntimeInterceptor,
        WorkflowRuntime, DaprWorkflowClient,
        ScheduleWorkflowInput, CallActivityInput, CallChildWorkflowInput,
        ExecuteWorkflowInput, ExecuteActivityInput,
    )

    TRACE_ID_KEY = 'otel.trace_id'

    class TracingClientInterceptor(BaseClientInterceptor):
        def __init__(self, get_trace: Callable[[], str]):
            self._get = get_trace
        def schedule_new_workflow(self, input: ScheduleWorkflowInput, next):
            md = dict(input.metadata or {})
            md.setdefault(TRACE_ID_KEY, self._get())
            return next(ScheduleWorkflowInput(
                workflow_name=input.workflow_name,
                args=input.args,
                instance_id=input.instance_id,
                start_at=input.start_at,
                reuse_id_policy=input.reuse_id_policy,
                metadata=md,
                local_context=input.local_context,
            ))

    class TracingWorkflowOutboundInterceptor(BaseWorkflowOutboundInterceptor):
        def __init__(self, get_trace: Callable[[], str]):
            self._get = get_trace
        def call_activity(self, input: CallActivityInput, next):
            md = dict(input.metadata or {})
            md.setdefault(TRACE_ID_KEY, self._get())
            return next(type(input)(
                activity_name=input.activity_name,
                args=input.args,
                retry_policy=input.retry_policy,
                workflow_ctx=input.workflow_ctx,
                metadata=md,
                local_context=input.local_context,
            ))
        def call_child_workflow(self, input: CallChildWorkflowInput, next):
            md = dict(input.metadata or {})
            md.setdefault(TRACE_ID_KEY, self._get())
            return next(type(input)(
                workflow_name=input.workflow_name,
                args=input.args,
                instance_id=input.instance_id,
                workflow_ctx=input.workflow_ctx,
                metadata=md,
                local_context=input.local_context,
            ))

    class TracingRuntimeInterceptor(BaseRuntimeInterceptor):
        def execute_workflow(self, input: ExecuteWorkflowInput, next):
            if not input.ctx.is_replaying:
                _trace_id = (input.metadata or {}).get(TRACE_ID_KEY)
                # start workflow span here
            return next(input)
        def execute_activity(self, input: ExecuteActivityInput, next):
            _trace_id = (input.metadata or {}).get(TRACE_ID_KEY)
            # start activity span here
            return next(input)

    rt = WorkflowRuntime(
        runtime_interceptors=[TracingRuntimeInterceptor()],
        workflow_outbound_interceptors=[TracingWorkflowOutboundInterceptor(lambda: 'trace-123')],
    )
    client = DaprWorkflowClient(interceptors=[TracingClientInterceptor(lambda: 'trace-123')])

See the full runnable example in ``ext/dapr-ext-workflow/examples/tracing_interceptors_example.py``.

Notes
~~~~~

- User functions never see the envelope keys; they get the same input as before.
- Only string keys/values should be stored in ``metadata``; enforce size limits and redaction
  policies as needed.
- With newer durabletask-python, the engine provides deterministic context fields on
  ``OrchestrationContext``/``ActivityContext`` that the SDK surfaces via
  ``ctx.execution_info``/``activity_ctx.execution_info``: ``workflow_name``,
  ``parent_instance_id``, ``history_event_sequence``, and ``attempt``. The SDK no longer
  stamps parent linkage in metadata when these are present.

Notes
-----

- Interceptors are synchronous and must not perform I/O in orchestrators. Activities may perform
  I/O inside the user function; interceptor code should remain fast and replay-safe.
- Client interceptors are applied when calling ``DaprWorkflowClient.schedule_new_workflow(...)`` and
  when orchestrators call ``ctx.call_activity(...)`` or ``ctx.call_child_workflow(...)``.

Legacy middleware
~~~~~~~~~~~~~~~~~

Earlier drafts referenced a middleware hook API. It has been removed in favor of interceptors.
Use the interceptor types described above for new development.

Best-effort sandbox
~~~~~~~~~~~~~~~~~~~

Opt-in scoped compatibility mode maps ``asyncio.sleep``, ``random``, ``uuid.uuid4``, and ``time.time`` to deterministic equivalents during workflow execution. Use ``sandbox_mode="best_effort"`` or ``"strict"`` when registering async workflows. Strict mode blocks ``asyncio.create_task`` in orchestrators.

Examples
~~~~~~~~

See ``ext/dapr-ext-workflow/examples`` for:

- ``async_activity_sequence.py``
- ``async_external_event.py``
- ``async_sub_orchestrator.py``

Determinism and semantics
~~~~~~~~~~~~~~~~~~~~~~~~~

- ``when_any`` losers: the first-completer result is returned; non-winning awaitables are ignored deterministically (no additional commands are emitted by the orchestrator for cancellation). This ensures replay stability. Integration behavior with the sidecar is subject to the Durable Task scheduler; the orchestrator does not actively cancel losers.
- Suspension and termination: when an instance is suspended, only new external events are buffered while replay continues to reconstruct state; async orchestrators can inspect ``ctx.is_suspended`` if exposed by the runtime. Termination completes the orchestrator with TERMINATED status and does not raise into the coroutine. End-to-end confirmation requires running against a sidecar; unit tests in this repo do not start a sidecar.

Async patterns
~~~~~~~~~~~~~~

- Activities

  - Call: ``await ctx.call_activity(activity_fn, input=..., retry_policy=...)``
  - Activity functions can be ``def`` or ``async def``. When ``async def`` is used, the runtime awaits them.

- Timers

  - Create a durable timer: ``await ctx.create_timer(seconds|timedelta)``

- External events

  - Wait: ``await ctx.wait_for_external_event(name)``
  - Raise (from client): ``DaprWorkflowClient.raise_workflow_event(instance_id, name, data)``

- Concurrency

  - All: ``results = await ctx.when_all([ ...awaitables... ])``
  - Any: ``first = await ctx.when_any([ ...awaitables... ])`` (non-winning awaitables are ignored deterministically)

- Child workflows

  - Call: ``await ctx.call_child_workflow(workflow_fn, input=..., retry_policy=...)``

- Deterministic utilities

  - ``ctx.now()`` returns orchestration time from history
  - ``ctx.random()`` returns a deterministic PRNG
  - ``ctx.uuid4()`` returns a PRNG-derived deterministic UUID

Runtime compatibility
---------------------

- ``ctx.is_suspended`` is surfaced if provided by the underlying runtime/context version; behavior may vary by Durable Task build. Integration tests that validate suspension semantics are gated behind a sidecar harness.

when_any losers diagnostics (integration)
-----------------------------------------

- When the sidecar exposes command diagnostics, you can assert only a single command set is emitted for a ``when_any`` (the orchestrator completes after the first winner without emitting cancels). Until then, unit tests assert single-yield behavior and README documents the expected semantics.

Micro-bench guidance
--------------------

- The coroutine-to-generator driver yields at each deterministic suspension point and avoids polling. In practice, overhead vs. generator orchestrators is negligible relative to activity I/O. To measure locally:

  - Create paired generator/async orchestrators that call N no-op activities and 1 timer.
  - Drive them against a local sidecar and compare wall-clock per activation and total completion time.
  - Ensure identical history/inputs; differences should be within noise vs. activity latency.

Notes
-----

- Orchestrators authored as ``async def`` are not driven by a global event loop you start. The Durable Task worker drives them via a coroutine-to-generator bridge; do not call ``asyncio.run`` around orchestrators.
- Use ``WorkflowRuntime.workflow`` with an ``async def`` (auto-detected) or ``WorkflowRuntime.async_workflow`` to register async orchestrators.

Why async without an event loop?
--------------------------------

- Each ``await`` in an async orchestrator corresponds to a deterministic Durable Task decision (activity, timer, external event, ``when_all/any``). The worker advances the coroutine by sending results/exceptions back in, preserving replay and ordering.
- This gives you the readability and structure of ``async/await`` while enforcing workflow determinism (no ad-hoc I/O in orchestrators; all I/O happens in activities).
- The pattern follows other workflow engines (e.g., Durable Functions/Temporal): async authoring for clarity, runtime-driven scheduling for correctness.

References
----------

* `Dapr <https://github.com/dapr/dapr>`_
* `Dapr Python-SDK <https://github.com/dapr/python-sdk>`_
