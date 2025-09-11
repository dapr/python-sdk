# -*- coding: utf-8 -*-

"""
Example: Interceptors for context propagation (client + runtime).

This example shows how to:
 - Define a small context (dict) carried via contextvars
 - Implement ClientInterceptor to inject that context into outbound inputs
 - Implement RuntimeInterceptor to restore the context before user code runs
 - Wire interceptors into WorkflowRuntime and DaprWorkflowClient

Note: Scheduling/running requires a Dapr sidecar. This file focuses on the wiring pattern.
"""

from __future__ import annotations

import contextvars
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

# A simple context carried across boundaries
_current_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    'wf_ctx', default=None
)


def set_ctx(ctx: dict[str, Any] | None) -> None:
    _current_ctx.set(ctx)


def get_ctx() -> dict[str, Any] | None:
    return _current_ctx.get()


def _merge_ctx(args: Any) -> Any:
    ctx = get_ctx()
    if ctx and isinstance(args, dict) and 'context' not in args:
        return {**args, 'context': ctx}
    return args


class ContextClientInterceptor(BaseClientInterceptor):
    def schedule_new_workflow(
        self, input: ScheduleWorkflowInput, nxt: Callable[[ScheduleWorkflowInput], Any]
    ) -> Any:  # type: ignore[override]
        input = ScheduleWorkflowInput(
            workflow_name=input.workflow_name,
            args=_merge_ctx(input.args),
            instance_id=input.instance_id,
            start_at=input.start_at,
            reuse_id_policy=input.reuse_id_policy,
        )
        return nxt(input)


class ContextWorkflowOutboundInterceptor(BaseWorkflowOutboundInterceptor):
    def call_child_workflow(
        self, input: CallChildWorkflowInput, nxt: Callable[[CallChildWorkflowInput], Any]
    ) -> Any:
        return nxt(
            CallChildWorkflowInput(
                workflow_name=input.workflow_name,
                args=_merge_ctx(input.args),
                instance_id=input.instance_id,
                workflow_ctx=input.workflow_ctx,
                metadata=input.metadata,
                local_context=input.local_context,
            )
        )

    def call_activity(
        self, input: CallActivityInput, nxt: Callable[[CallActivityInput], Any]
    ) -> Any:
        return nxt(
            CallActivityInput(
                activity_name=input.activity_name,
                args=_merge_ctx(input.args),
                retry_policy=input.retry_policy,
                workflow_ctx=input.workflow_ctx,
                metadata=input.metadata,
                local_context=input.local_context,
            )
        )


class ContextRuntimeInterceptor(BaseRuntimeInterceptor):
    def execute_workflow(
        self, input: ExecuteWorkflowInput, nxt: Callable[[ExecuteWorkflowInput], Any]
    ) -> Any:  # type: ignore[override]
        if isinstance(input.input, dict) and 'context' in input.input:
            set_ctx(input.input['context'])
        try:
            return nxt(input)
        finally:
            set_ctx(None)

    def execute_activity(
        self, input: ExecuteActivityInput, nxt: Callable[[ExecuteActivityInput], Any]
    ) -> Any:  # type: ignore[override]
        if isinstance(input.input, dict) and 'context' in input.input:
            set_ctx(input.input['context'])
        try:
            return nxt(input)
        finally:
            set_ctx(None)


# Example workflow and activity
def activity_log(ctx, data: dict[str, Any]) -> str:  # noqa: ANN001 (example)
    # Access restored context inside activity via contextvars
    return f'ok:{get_ctx()}'


def workflow_example(ctx, x: int):  # noqa: ANN001 (example)
    y = yield ctx.call_activity(activity_log, input={'msg': 'hello'})
    return y


def wire_up() -> tuple[WorkflowRuntime, DaprWorkflowClient]:
    runtime = WorkflowRuntime(
        runtime_interceptors=[ContextRuntimeInterceptor()],
        workflow_outbound_interceptors=[ContextWorkflowOutboundInterceptor()],
    )
    client = DaprWorkflowClient(interceptors=[ContextClientInterceptor()])

    # Register workflow/activity
    runtime.workflow(name='example')(workflow_example)
    runtime.activity(name='activity_log')(activity_log)
    return runtime, client


if __name__ == '__main__':
    # This section demonstrates how you would set a context and schedule a workflow.
    # Requires a running Dapr sidecar to actually execute.
    rt, cli = wire_up()
    set_ctx({'tenant': 'acme', 'request_id': 'r-123'})
    # instance_id = cli.schedule_new_workflow(workflow_example, input={'x': 1})
    # print('scheduled:', instance_id)
    # rt.start(); rt.wait_for_ready(); ...
    pass
