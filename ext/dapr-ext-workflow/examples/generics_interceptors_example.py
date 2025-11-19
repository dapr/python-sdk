from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import List

from dapr.ext.workflow import (
    DaprWorkflowClient,
    WorkflowRuntime,
)
from dapr.ext.workflow.interceptors import (
    BaseClientInterceptor,
    BaseRuntimeInterceptor,
    BaseWorkflowOutboundInterceptor,
    CallActivityRequest,
    CallChildWorkflowRequest,
    ContinueAsNewRequest,
    ExecuteActivityRequest,
    ExecuteWorkflowRequest,
    ScheduleWorkflowRequest,
)

# ------------------------------
# Typed payloads carried by interceptors
# ------------------------------


@dataclass
class MyWorkflowInput:
    question: str
    tags: List[str]


@dataclass
class MyActivityInput:
    name: str
    count: int


# ------------------------------
# Interceptors with generics + minimal (de)serialization
# ------------------------------


class MyClientInterceptor(BaseClientInterceptor[MyWorkflowInput]):
    def schedule_new_workflow(
        self,
        input: ScheduleWorkflowRequest[MyWorkflowInput],
        nxt,
    ) -> str:
        # Ensure wire format is JSON-serializable (dict)
        payload = (
            asdict(input.input) if hasattr(input.input, '__dataclass_fields__') else input.input
        )
        shaped = ScheduleWorkflowRequest[MyWorkflowInput](
            workflow_name=input.workflow_name,
            input=payload,  # type: ignore[arg-type]
            instance_id=input.instance_id,
            start_at=input.start_at,
            reuse_id_policy=input.reuse_id_policy,
            metadata=input.metadata,
        )
        return nxt(shaped)


class MyRuntimeInterceptor(BaseRuntimeInterceptor[MyWorkflowInput, MyActivityInput]):
    def execute_workflow(
        self,
        input: ExecuteWorkflowRequest[MyWorkflowInput],
        nxt,
    ):
        # Convert inbound dict into typed model for workflow code
        data = input.input
        if isinstance(data, dict) and 'question' in data:
            input.input = MyWorkflowInput(
                question=data.get('question', ''), tags=list(data.get('tags', []))
            )  # type: ignore[assignment]
        return nxt(input)

    def execute_activity(
        self,
        input: ExecuteActivityRequest[MyActivityInput],
        nxt,
    ):
        data = input.input
        if isinstance(data, dict) and 'name' in data:
            input.input = MyActivityInput(
                name=data.get('name', ''), count=int(data.get('count', 0))
            )  # type: ignore[assignment]
        return nxt(input)


class MyOutboundInterceptor(BaseWorkflowOutboundInterceptor[MyWorkflowInput, MyActivityInput]):
    def call_child_workflow(
        self,
        input: CallChildWorkflowRequest[MyWorkflowInput],
        nxt,
    ):
        # Convert typed payload back to wire before sending
        payload = (
            asdict(input.input) if hasattr(input.input, '__dataclass_fields__') else input.input
        )
        shaped = CallChildWorkflowRequest[MyWorkflowInput](
            workflow_name=input.workflow_name,
            input=payload,  # type: ignore[arg-type]
            instance_id=input.instance_id,
            workflow_ctx=input.workflow_ctx,
            metadata=input.metadata,
        )
        return nxt(shaped)

    def continue_as_new(
        self,
        input: ContinueAsNewRequest[MyWorkflowInput],
        nxt,
    ):
        payload = (
            asdict(input.input) if hasattr(input.input, '__dataclass_fields__') else input.input
        )
        shaped = ContinueAsNewRequest[MyWorkflowInput](
            input=payload,  # type: ignore[arg-type]
            workflow_ctx=input.workflow_ctx,
            metadata=input.metadata,
        )
        return nxt(shaped)

    def call_activity(
        self,
        input: CallActivityRequest[MyActivityInput],
        nxt,
    ):
        payload = (
            asdict(input.input) if hasattr(input.input, '__dataclass_fields__') else input.input
        )
        shaped = CallActivityRequest[MyActivityInput](
            activity_name=input.activity_name,
            input=payload,  # type: ignore[arg-type]
            retry_policy=input.retry_policy,
            workflow_ctx=input.workflow_ctx,
            metadata=input.metadata,
        )
        return nxt(shaped)


# ------------------------------
# Minimal runnable example with sidecar
# ------------------------------


def main() -> None:
    # Expect DAPR_GRPC_ENDPOINT (e.g., dns:127.0.0.1:56179) to be set for local sidecar/dev hub
    ep = os.getenv('DAPR_GRPC_ENDPOINT')
    if not ep:
        print('WARNING: DAPR_GRPC_ENDPOINT not set; default sidecar address will be used')

    # Build runtime with interceptors
    runtime = WorkflowRuntime(
        runtime_interceptors=[MyRuntimeInterceptor()],
        workflow_outbound_interceptors=[MyOutboundInterceptor()],
    )

    # Register a simple activity
    @runtime.activity(name='greet')
    def greet(_ctx, x: dict | None = None) -> str:  # wire format at activity boundary is dict
        x = x or {}
        return f'Hello {x.get("name", "world")} x{x.get("count", 0)}'

    # Register an async workflow that calls the activity once
    @runtime.async_workflow(name='wf_greet')
    async def wf_greet(ctx, arg: MyWorkflowInput | dict | None = None):
        # At this point, runtime interceptor converted inbound to MyWorkflowInput
        if isinstance(arg, MyWorkflowInput):
            act_in = MyActivityInput(name=arg.question, count=len(arg.tags))
        else:
            # Fallback if interceptor not present
            d = arg or {}
            act_in = MyActivityInput(name=str(d.get('question', '')), count=len(d.get('tags', [])))
        return await ctx.call_activity('greet', input=asdict(act_in))

    runtime.start()
    try:
        # Client with client-side interceptor for schedule typing
        client = DaprWorkflowClient(interceptors=[MyClientInterceptor()])
        wf_input = MyWorkflowInput(question='World', tags=['a', 'b'])
        instance_id = client.schedule_new_workflow(wf_greet, input=wf_input)
        print('Started instance:', instance_id)
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        print('Final status:', getattr(st, 'runtime_status', None))
        if st:
            print('Output:', st.to_json().get('serialized_output'))
    finally:
        runtime.shutdown()


if __name__ == '__main__':
    main()
