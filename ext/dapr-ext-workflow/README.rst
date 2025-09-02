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

Middleware (workflow/activity hooks)
------------------------------------

This extension supports pluggable middleware that can observe key workflow and activity lifecycle
events. Use middleware for cross-cutting concerns such as context propagation, replay-aware
logging/metrics, and policy enforcement.

- Register at runtime construction via ``WorkflowRuntime(middleware=[...])`` or use
  ``add_middleware`` at any time. Control behavior with ``set_middleware_policy``.
- Ordering: start/yield/resume hooks run in ascending registration order; complete/error hooks run
  in reverse order (stack semantics).
- Determinism: workflow/orchestrator hooks are synchronous (returned awaitables are not awaited).
  Activity hooks may be ``async`` and are awaited by the runtime.

.. code-block:: python

    from dapr.ext.workflow import (
        WorkflowRuntime,
        RuntimeMiddleware,
        MiddlewarePolicy,
        MiddlewareOrder,
    )

    class TraceContext(RuntimeMiddleware):
        def on_workflow_start(self, ctx, input):
            # restore trace context using contextvars (no I/O)
            pass

        async def on_activity_start(self, ctx, input):
            # async is allowed in activities
            pass

    rt = WorkflowRuntime(
        middleware=[TraceContext()],
        middleware_policy=MiddlewarePolicy.CONTINUE_ON_ERROR,
    )

    # Or later at runtime
    rt.add_middleware(TraceContext(), order=MiddlewareOrder.DEFAULT)
    rt.set_middleware_policy(MiddlewarePolicy.RAISE_ON_ERROR)

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
