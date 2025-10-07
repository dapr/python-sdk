# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Callable

from dapr.ext.workflow import (
    BaseClientInterceptor,
    BaseRuntimeInterceptor,
    BaseWorkflowOutboundInterceptor,
    CallActivityInput,
    CallChildWorkflowInput,
    DaprWorkflowClient,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    ScheduleWorkflowInput,
    WorkflowRuntime,
)

TRACE_ID_KEY = 'otel.trace_id'
SPAN_ID_KEY = 'otel.span_id'


class TracingClientInterceptor(BaseClientInterceptor):
    def __init__(self, get_current_trace: Callable[[], tuple[str, str]]):
        self._get = get_current_trace

    def schedule_new_workflow(self, input: ScheduleWorkflowInput, next):  # type: ignore[override]
        trace_id, span_id = self._get()
        md = dict(input.metadata or {})
        md[TRACE_ID_KEY] = trace_id
        md[SPAN_ID_KEY] = span_id
        return next(
            ScheduleWorkflowInput(
                workflow_name=input.workflow_name,
                args=input.args,
                instance_id=input.instance_id,
                start_at=input.start_at,
                reuse_id_policy=input.reuse_id_policy,
                metadata=md,
                local_context=input.local_context,
            )
        )


class TracingRuntimeInterceptor(BaseRuntimeInterceptor):
    def __init__(self, on_span: Callable[[str, dict[str, str]], Any]):
        self._on_span = on_span

    def execute_workflow(self, input: ExecuteWorkflowInput, next):  # type: ignore[override]
        # Suppress spans during replay
        if not input.ctx.is_replaying:
            self._on_span('dapr:executeWorkflow', input.metadata or {})
        return next(input)

    def execute_activity(self, input: ExecuteActivityInput, next):  # type: ignore[override]
        self._on_span('dapr:executeActivity', input.metadata or {})
        return next(input)


class TracingWorkflowOutboundInterceptor(BaseWorkflowOutboundInterceptor):
    def __init__(self, get_current_trace: Callable[[], tuple[str, str]]):
        self._get = get_current_trace

    def call_activity(self, input: CallActivityInput, next):  # type: ignore[override]
        trace_id, span_id = self._get()
        md = dict((input.metadata or {}) or {})
        md[TRACE_ID_KEY] = md.get(TRACE_ID_KEY, trace_id)
        md[SPAN_ID_KEY] = span_id
        return next(
            type(input)(
                activity_name=input.activity_name,
                args=input.args,
                retry_policy=input.retry_policy,
                workflow_ctx=input.workflow_ctx,
                metadata=md,
                local_context=input.local_context,
            )
        )

    def call_child_workflow(self, input: CallChildWorkflowInput, next):  # type: ignore[override]
        trace_id, span_id = self._get()
        md = dict((input.metadata or {}) or {})
        md[TRACE_ID_KEY] = md.get(TRACE_ID_KEY, trace_id)
        md[SPAN_ID_KEY] = span_id
        return next(
            type(input)(
                workflow_name=input.workflow_name,
                args=input.args,
                instance_id=input.instance_id,
                workflow_ctx=input.workflow_ctx,
                metadata=md,
                local_context=input.local_context,
            )
        )


def example_usage():
    # Simplified trace getter and span recorder
    def _get_trace():
        return ('trace-123', 'span-abc')

    spans: list[tuple[str, dict[str, str]]] = []

    def _on_span(name: str, attrs: dict[str, str]):
        spans.append((name, attrs))

    runtime = WorkflowRuntime(
        runtime_interceptors=[TracingRuntimeInterceptor(_on_span)],
        workflow_outbound_interceptors=[TracingWorkflowOutboundInterceptor(_get_trace)],
    )

    client = DaprWorkflowClient(interceptors=[TracingClientInterceptor(_get_trace)])

    # Register and run as you would normally; spans list can be asserted in tests
    return runtime, client, spans


if __name__ == '__main__':  # pragma: no cover
    example_usage()
