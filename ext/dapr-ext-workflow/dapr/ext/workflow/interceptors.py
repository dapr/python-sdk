# -*- coding: utf-8 -*-

"""
Interceptor interfaces and chain utilities for the Dapr Workflow SDK.

This replaces ad-hoc middleware hook patterns with composable client/runtime interceptors,
providing a single enter/exit around calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

# ------------------------------
# Client-side interceptor surface
# ------------------------------

@dataclass
class ScheduleInput:
    workflow_name: str
    args: Any
    instance_id: Optional[str]
    start_at: Optional[Any]
    reuse_id_policy: Optional[Any]


@dataclass
class StartChildInput:
    workflow_name: str
    args: Any
    instance_id: Optional[str]


@dataclass
class StartActivityInput:
    activity_name: str
    args: Any
    retry_policy: Optional[Any]


class ClientInterceptor(Protocol):
    def schedule_new_workflow(self, input: ScheduleInput, next: Callable[[ScheduleInput], Any]) -> Any: ...
    def start_child_workflow(self, input: StartChildInput, next: Callable[[StartChildInput], Any]) -> Any: ...
    def start_activity(self, input: StartActivityInput, next: Callable[[StartActivityInput], Any]) -> Any: ...


# -------------------------------
# Runtime-side interceptor surface
# -------------------------------

@dataclass
class ExecuteWorkflowInput:
    ctx: Any
    input: Any


@dataclass
class ExecuteActivityInput:
    ctx: Any
    input: Any


class RuntimeInterceptor(Protocol):
    def execute_workflow(self, input: ExecuteWorkflowInput, next: Callable[[ExecuteWorkflowInput], Any]) -> Any: ...
    def execute_activity(self, input: ExecuteActivityInput, next: Callable[[ExecuteActivityInput], Any]) -> Any: ...


# ------------------------------
# Helper: chain composition
# ------------------------------

def compose_client_chain(interceptors: list[ClientInterceptor], terminal: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Compose client interceptors into a single callable.

    Interceptors are applied in list order; each receives a `next`.
    """
    next_fn = terminal
    for icpt in reversed(interceptors or []):
        def make_next(curr_icpt: ClientInterceptor, nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                # Dispatch based on input type
                if isinstance(input, ScheduleInput):
                    if hasattr(curr_icpt, 'schedule_new_workflow'):
                        return curr_icpt.schedule_new_workflow(input, nxt)
                if isinstance(input, StartChildInput):
                    if hasattr(curr_icpt, 'start_child_workflow'):
                        return curr_icpt.start_child_workflow(input, nxt)
                if isinstance(input, StartActivityInput):
                    if hasattr(curr_icpt, 'start_activity'):
                        return curr_icpt.start_activity(input, nxt)
                return nxt(input)
            return runner
        next_fn = make_next(icpt, next_fn)
    return next_fn


def compose_runtime_chain(interceptors: list[RuntimeInterceptor], terminal: Callable[[Any], Any]):
    """Compose runtime interceptors into a single callable (synchronous)."""
    next_fn = terminal
    for icpt in reversed(interceptors or []):
        def make_next(curr_icpt: RuntimeInterceptor, nxt: Callable[[Any], Any]):
            def runner(input: Any) -> Any:
                if isinstance(input, ExecuteWorkflowInput):
                    if hasattr(curr_icpt, 'execute_workflow'):
                        return curr_icpt.execute_workflow(input, nxt)
                if isinstance(input, ExecuteActivityInput):
                    if hasattr(curr_icpt, 'execute_activity'):
                        return curr_icpt.execute_activity(input, nxt)
                return nxt(input)
            return runner
        next_fn = make_next(icpt, next_fn)
    return next_fn
