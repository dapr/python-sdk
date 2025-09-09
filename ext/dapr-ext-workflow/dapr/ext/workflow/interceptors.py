# -*- coding: utf-8 -*-

"""
Interceptor interfaces and chain utilities for the Dapr Workflow SDK.

This replaces ad-hoc middleware hook patterns with composable client/runtime interceptors,
providing a single enter/exit around calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_context import WorkflowContext

# ------------------------------
# Client-side interceptor surface
# ------------------------------

@dataclass
class ScheduleWorkflowInput:
    workflow_name: str
    args: Any
    instance_id: Optional[str]
    start_at: Optional[Any]
    reuse_id_policy: Optional[Any]


@dataclass
class CallChildWorkflowInput:
    workflow_name: str
    args: Any
    instance_id: Optional[str]
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None


@dataclass
class CallActivityInput:
    activity_name: str
    args: Any
    retry_policy: Optional[Any]
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None


class ClientInterceptor(Protocol):
    def schedule_new_workflow(self, input: ScheduleWorkflowInput, next: Callable[[ScheduleWorkflowInput], Any]) -> Any: ...
    def call_child_workflow(self, input: CallChildWorkflowInput, next: Callable[[CallChildWorkflowInput], Any]) -> Any: ...
    def call_activity(self, input: CallActivityInput, next: Callable[[CallActivityInput], Any]) -> Any: ...


# -------------------------------
# Runtime-side interceptor surface
# -------------------------------

@dataclass
class ExecuteWorkflowInput:
    ctx: WorkflowContext
    input: Any


@dataclass
class ExecuteActivityInput:
    ctx: WorkflowActivityContext
    input: Any


class RuntimeInterceptor(Protocol):
    def execute_workflow(self, input: ExecuteWorkflowInput, next: Callable[[ExecuteWorkflowInput], Any]) -> Any: ...
    def execute_activity(self, input: ExecuteActivityInput, next: Callable[[ExecuteActivityInput], Any]) -> Any: ...


# ------------------------------
# Convenience base classes (devex)
# ------------------------------

class BaseClientInterceptor:
    """Subclass this to get method name completion and safe defaults.

    Override any of the methods to customize behavior. By default, these
    methods simply call `next` unchanged.
    """

    def schedule_new_workflow(self, input: ScheduleWorkflowInput, next: Callable[[ScheduleWorkflowInput], Any]) -> Any:  # noqa: D401
        return next(input)

    def call_child_workflow(self, input: CallChildWorkflowInput, next: Callable[[CallChildWorkflowInput], Any]) -> Any:  # noqa: D401
        return next(input)

    def call_activity(self, input: CallActivityInput, next: Callable[[CallActivityInput], Any]) -> Any:  # noqa: D401
        return next(input)


class BaseRuntimeInterceptor:
    """Subclass this to get method name completion and safe defaults."""

    def execute_workflow(self, input: ExecuteWorkflowInput, next: Callable[[ExecuteWorkflowInput], Any]) -> Any:  # noqa: D401
        return next(input)

    def execute_activity(self, input: ExecuteActivityInput, next: Callable[[ExecuteActivityInput], Any]) -> Any:  # noqa: D401
        return next(input)

# ------------------------------
# Helper: chain composition
# ------------------------------

def compose_client_chain(interceptors: list['BaseClientInterceptor'], terminal: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Compose client interceptors into a single callable.

    Interceptors are applied in list order; each receives a `next`.
    """
    next_fn = terminal
    for icpt in reversed(interceptors or []):
        def make_next(curr_icpt: 'BaseClientInterceptor', nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                if isinstance(input, ScheduleWorkflowInput):
                    return curr_icpt.schedule_new_workflow(input, nxt)
                if isinstance(input, CallChildWorkflowInput):
                    return curr_icpt.call_child_workflow(input, nxt)
                if isinstance(input, CallActivityInput):
                    return curr_icpt.call_activity(input, nxt)
                return nxt(input)
            return runner
        next_fn = make_next(icpt, next_fn)
    return next_fn


def compose_runtime_chain(interceptors: list['BaseRuntimeInterceptor'], terminal: Callable[[Any], Any]):
    """Compose runtime interceptors into a single callable (synchronous)."""
    next_fn = terminal
    for icpt in reversed(interceptors or []):
        def make_next(curr_icpt: 'BaseRuntimeInterceptor', nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                if isinstance(input, ExecuteWorkflowInput):
                    return curr_icpt.execute_workflow(input, nxt)
                if isinstance(input, ExecuteActivityInput):
                    return curr_icpt.execute_activity(input, nxt)
                return nxt(input)
            return runner
        next_fn = make_next(icpt, next_fn)
    return next_fn
