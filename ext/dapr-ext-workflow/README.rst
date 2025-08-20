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

- Register async workflows using ``WorkflowRuntime.async_workflow`` or ``register_async_workflow``.
- Use ``AsyncWorkflowContext`` for deterministic operations:

  - Activities: ``await ctx.activity(activity_fn, input=...)``
  - Sub-orchestrators: ``await ctx.sub_orchestrator(workflow_fn, input=...)``
  - Timers: ``await ctx.sleep(seconds|timedelta)``
  - External events: ``await ctx.wait_for_external_event(name)``
  - Concurrency: ``await ctx.when_all([...])``, ``await ctx.when_any([...])``
  - Deterministic utils: ``ctx.now()``, ``ctx.random()``, ``ctx.uuid4()``

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

References
----------

* `Dapr <https://github.com/dapr/dapr>`_
* `Dapr Python-SDK <https://github.com/dapr/python-sdk>`_
