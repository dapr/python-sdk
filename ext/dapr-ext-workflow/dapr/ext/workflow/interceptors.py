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
    # Extra context (durable string map, in-process objects)
    metadata: Optional[dict[str, str]] = None
    local_context: Optional[dict[str, Any]] = None


@dataclass
class CallChildWorkflowInput:
    workflow_name: str
    args: Any
    instance_id: Optional[str]
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None
    # Extra context (durable string map, in-process objects)
    metadata: Optional[dict[str, str]] = None
    local_context: Optional[dict[str, Any]] = None


@dataclass
class CallActivityInput:
    activity_name: str
    args: Any
    retry_policy: Optional[Any]
    # Optional workflow context for outbound calls made inside workflows
    workflow_ctx: Any | None = None
    # Extra context (durable string map, in-process objects)
    metadata: Optional[dict[str, str]] = None
    local_context: Optional[dict[str, Any]] = None


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
    # Durable metadata and in-process context
    metadata: Optional[dict[str, str]] = None
    local_context: Optional[dict[str, Any]] = None


@dataclass
class ExecuteActivityInput:
    ctx: WorkflowActivityContext
    input: Any
    # Durable metadata and in-process context
    metadata: Optional[dict[str, str]] = None
    local_context: Optional[dict[str, Any]] = None


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


# ------------------------------
# Helper: envelope for durable metadata
# ------------------------------

_META_KEY = '__dapr_meta__'
_META_VERSION = 1
_PAYLOAD_KEY = '__dapr_payload__'


def wrap_payload_with_metadata(payload: Any, metadata: Optional[dict[str, str]] | None) -> Any:
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


def unwrap_payload_with_metadata(obj: Any) -> tuple[Any, Optional[dict[str, str]]]:
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
