"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Protocol, TypeVar

from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_context import WorkflowContext

# Type variables for generic interceptor payload typing
TInput = TypeVar('TInput')
TWorkflowInput = TypeVar('TWorkflowInput')
TActivityInput = TypeVar('TActivityInput')

"""
Interceptor interfaces and chain utilities for the Dapr Workflow SDK.

Providing a single enter/exit around calls.

IMPORTANT: Generator wrappers for async workflows
--------------------------------------------------
When writing runtime interceptors that touch workflow execution, be careful with generator
handling. If an interceptor obtains a workflow generator from user code (e.g., an async
orchestrator adapted into a generator) it must not manually iterate it using a for-loop
and yield the produced items. Doing so breaks send()/throw() propagation back into the
inner generator, which can cause resumed results from the durable runtime to be dropped
and appear as None to awaiters.

Best practices:
- If the interceptor participates in composition and needs to return the generator,
  return it directly (do not iterate it).
- If the interceptor must wrap the generator, always use "yield from inner_gen" so that
  send()/throw() are forwarded correctly.

Context managers with async workflows
--------------------------------------
When using context managers (like ExitStack, logging contexts, or trace contexts) in an
interceptor for async workflows, be aware that calling `next(input)` returns a generator
object immediately, NOT the final result. The generator executes later when the durable
task runtime drives it.

If you need a context manager to remain active during the workflow execution:

**WRONG - Context exits before workflow runs:**

    def execute_workflow(self, input: ExecuteWorkflowRequest, next):
        with setup_context():
            return next(input)  # Returns generator, context exits immediately!

**CORRECT - Context stays active throughout execution:**

    def execute_workflow(self, input: ExecuteWorkflowRequest, next):
        def wrapper():
            with setup_context():
                gen = next(input)
                yield from gen  # Keep context alive while generator executes
        return wrapper()

For more complex scenarios with ExitStack or async context managers, wrap the generator
with `yield from` to ensure your context spans the entire workflow execution, including
all replay and continuation events.

Example with ExitStack:

    def execute_workflow(self, input: ExecuteWorkflowRequest, next):
        def wrapper():
            with ExitStack() as stack:
                # Set up contexts (trace, logging, etc.)
                stack.enter_context(trace_context(...))
                stack.enter_context(logging_context(...))

                # Get the generator from the next interceptor/handler
                gen = next(input)

                # Keep contexts alive while generator executes
                yield from gen
        return wrapper()

This pattern ensures your context manager remains active during:
- Initial workflow execution
- Replays from durable state
- Continuation after awaits
- Activity calls and child workflow invocations
"""


# Context metadata propagation
# ----------------------------
# "metadata" is a durable, string-only map. It is serialized on the wire and propagates across
# boundaries (client → runtime → activity/child), surviving replays/retries. Use it when downstream
# components must observe the value. In-process ephemeral state should be handled within interceptors
# without attempting to propagate across process boundaries.


# ------------------------------
# Client-side interceptor surface
# ------------------------------


@dataclass
class ScheduleWorkflowRequest(Generic[TInput]):
    workflow_name: str
    input: TInput
    instance_id: str | None
    start_at: Any | None
    reuse_id_policy: Any | None
    # Durable context serialized and propagated across boundaries
    metadata: dict[str, str] | None = None


@dataclass
class CallChildWorkflowRequest(Generic[TInput]):
    workflow_name: str
    input: TInput
    instance_id: str | None
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None
    # Durable context serialized and propagated across boundaries
    metadata: dict[str, str] | None = None


@dataclass
class ContinueAsNewRequest(Generic[TInput]):
    input: TInput
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None
    # Durable context serialized and propagated across boundaries
    metadata: dict[str, str] | None = None


@dataclass
class CallActivityRequest(Generic[TInput]):
    activity_name: str
    input: TInput
    retry_policy: Any | None
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None
    # Durable context serialized and propagated across boundaries
    metadata: dict[str, str] | None = None


class ClientInterceptor(Protocol, Generic[TInput]):
    def schedule_new_workflow(
        self,
        input: ScheduleWorkflowRequest[TInput],
        next: Callable[[ScheduleWorkflowRequest[TInput]], Any],
    ) -> Any:
        ...


# -------------------------------
# Runtime-side interceptor surface
# -------------------------------


@dataclass
class ExecuteWorkflowRequest(Generic[TInput]):
    ctx: WorkflowContext
    input: TInput
    # Durable metadata (runtime chain only; not injected into user code)
    metadata: dict[str, str] | None = None


@dataclass
class ExecuteActivityRequest(Generic[TInput]):
    ctx: WorkflowActivityContext
    input: TInput
    # Durable metadata (runtime chain only; not injected into user code)
    metadata: dict[str, str] | None = None


class RuntimeInterceptor(Protocol, Generic[TWorkflowInput, TActivityInput]):
    def execute_workflow(
        self,
        input: ExecuteWorkflowRequest[TWorkflowInput],
        next: Callable[[ExecuteWorkflowRequest[TWorkflowInput]], Any],
    ) -> Any:
        ...

    def execute_activity(
        self,
        input: ExecuteActivityRequest[TActivityInput],
        next: Callable[[ExecuteActivityRequest[TActivityInput]], Any],
    ) -> Any:
        ...


# ------------------------------
# Convenience base classes (devex)
# ------------------------------


class BaseClientInterceptor(Generic[TInput]):
    """Subclass this to get method name completion and safe defaults.

    Override any of the methods to customize behavior. By default, these
    methods simply call `next` unchanged.
    """

    def schedule_new_workflow(
        self,
        input: ScheduleWorkflowRequest[TInput],
        next: Callable[[ScheduleWorkflowRequest[TInput]], Any],
    ) -> Any:  # noqa: D401
        return next(input)

    # No workflow-outbound methods here; use WorkflowOutboundInterceptor for those


class BaseRuntimeInterceptor(Generic[TWorkflowInput, TActivityInput]):
    """Subclass this to get method name completion and safe defaults."""

    def execute_workflow(
        self,
        input: ExecuteWorkflowRequest[TWorkflowInput],
        next: Callable[[ExecuteWorkflowRequest[TWorkflowInput]], Any],
    ) -> Any:  # noqa: D401
        return next(input)

    def execute_activity(
        self,
        input: ExecuteActivityRequest[TActivityInput],
        next: Callable[[ExecuteActivityRequest[TActivityInput]], Any],
    ) -> Any:  # noqa: D401
        return next(input)


# ------------------------------
# Helper: chain composition
# ------------------------------


def compose_client_chain(
    interceptors: list[ClientInterceptor], terminal: Callable[[Any], Any]
) -> Callable[[Any], Any]:
    """Compose client interceptors into a single callable.

    Interceptors are applied in list order; each receives a ``next``.
    The ``terminal`` callable is the final handler invoked after all interceptors; it
    performs the base operation (e.g., scheduling the workflow) when the chain ends.
    """
    next_fn = terminal
    for icpt in reversed(interceptors or []):

        def make_next(curr_icpt: ClientInterceptor, nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                if isinstance(input, ScheduleWorkflowRequest):
                    return curr_icpt.schedule_new_workflow(input, nxt)
                return nxt(input)

            return runner

        next_fn = make_next(icpt, next_fn)
    return next_fn


# ------------------------------
# Workflow outbound interceptor surface
# ------------------------------


class WorkflowOutboundInterceptor(Protocol, Generic[TWorkflowInput, TActivityInput]):
    def call_child_workflow(
        self,
        input: CallChildWorkflowRequest[TWorkflowInput],
        next: Callable[[CallChildWorkflowRequest[TWorkflowInput]], Any],
    ) -> Any:
        ...

    def continue_as_new(
        self,
        input: ContinueAsNewRequest[TWorkflowInput],
        next: Callable[[ContinueAsNewRequest[TWorkflowInput]], Any],
    ) -> Any:
        ...

    def call_activity(
        self,
        input: CallActivityRequest[TActivityInput],
        next: Callable[[CallActivityRequest[TActivityInput]], Any],
    ) -> Any:
        ...


class BaseWorkflowOutboundInterceptor(Generic[TWorkflowInput, TActivityInput]):
    def call_child_workflow(
        self,
        input: CallChildWorkflowRequest[TWorkflowInput],
        next: Callable[[CallChildWorkflowRequest[TWorkflowInput]], Any],
    ) -> Any:
        return next(input)

    def continue_as_new(
        self,
        input: ContinueAsNewRequest[TWorkflowInput],
        next: Callable[[ContinueAsNewRequest[TWorkflowInput]], Any],
    ) -> Any:
        return next(input)

    def call_activity(
        self,
        input: CallActivityRequest[TActivityInput],
        next: Callable[[CallActivityRequest[TActivityInput]], Any],
    ) -> Any:
        return next(input)


# ------------------------------
# Backward-compat typing aliases
# ------------------------------


def compose_workflow_outbound_chain(
    interceptors: list[WorkflowOutboundInterceptor],
    terminal: Callable[[Any], Any],
) -> Callable[[Any], Any]:
    """Compose workflow outbound interceptors into a single callable.

    Interceptors are applied in list order; each receives a ``next``.
    The ``terminal`` callable is the final handler invoked after all interceptors; it
    performs the base operation (e.g., preparing outbound call args) when the chain ends.
    """
    next_fn = terminal
    for icpt in reversed(interceptors or []):

        def make_next(curr_icpt: WorkflowOutboundInterceptor, nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                # Dispatch to the appropriate outbound method on the interceptor
                if isinstance(input, CallActivityRequest):
                    return curr_icpt.call_activity(input, nxt)
                if isinstance(input, CallChildWorkflowRequest):
                    return curr_icpt.call_child_workflow(input, nxt)
                if isinstance(input, ContinueAsNewRequest):
                    return curr_icpt.continue_as_new(input, nxt)
                # Fallback to next if input type unknown
                return nxt(input)

            return runner

        next_fn = make_next(icpt, next_fn)
    return next_fn


# ------------------------------
# Helper: envelope for durable metadata
# ------------------------------

_META_KEY = '__dapr_meta__'
_META_VERSION = 1
_PAYLOAD_KEY = '__dapr_payload__'


def wrap_payload_with_metadata(payload: Any, metadata: dict[str, str] | None) -> Any:
    """If metadata is provided and non-empty, wrap payload in an envelope for persistence.

    Backward compatible: if metadata is falsy, return payload unchanged.
    """
    if metadata:
        return {
            _META_KEY: {
                'v': _META_VERSION,
                'metadata': metadata,
            },
            _PAYLOAD_KEY: payload,
        }
    return payload


def unwrap_payload_with_metadata(obj: Any) -> tuple[Any, dict[str, str] | None]:
    """Extract payload and metadata from envelope if present.

    Returns (payload, metadata_dict_or_none).
    """
    try:
        if isinstance(obj, dict) and _META_KEY in obj and _PAYLOAD_KEY in obj:
            meta = obj.get(_META_KEY) or {}
            md = meta.get('metadata') if isinstance(meta, dict) else None
            return obj.get(_PAYLOAD_KEY), md if isinstance(md, dict) else None
    except Exception:
        # Be robust: on any error, treat as raw payload
        pass
    return obj, None


def compose_runtime_chain(
    interceptors: list[RuntimeInterceptor], final_handler: Callable[[Any], Any]
):
    """Compose runtime interceptors into a single callable (synchronous).

    The ``final_handler`` callable is the final handler invoked after all interceptors; it
    performs the core operation (e.g., calling user workflow/activity or returning a
    workflow generator) when the chain ends.
    """
    next_fn = final_handler
    for icpt in reversed(interceptors or []):

        def make_next(curr_icpt: RuntimeInterceptor, nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                if isinstance(input, ExecuteWorkflowRequest):
                    return curr_icpt.execute_workflow(input, nxt)
                if isinstance(input, ExecuteActivityRequest):
                    return curr_icpt.execute_activity(input, nxt)
                return nxt(input)

            return runner

        next_fn = make_next(icpt, next_fn)
    return next_fn
