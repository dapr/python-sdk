# -*- coding: utf-8 -*-

"""
Example: Interceptors for context propagation using metadata envelope (RECOMMENDED).

This example demonstrates the recommended approach for context propagation:
 - Use metadata envelope for durable, transparent context propagation
 - Implement ClientInterceptor to set metadata when scheduling workflows
 - Implement RuntimeInterceptor to restore context from metadata before execution
 - Implement WorkflowOutboundInterceptor to propagate metadata to activities/children
 - Use the wrapper pattern with 'yield from' to keep context alive during execution

CRITICAL: Workflow interceptors MUST use the wrapper pattern and return the result:
    def execute_workflow(self, request, nxt):
        def wrapper():
            setup_context()
            try:
                gen = nxt(request)
                result = yield from gen     # Keep context alive
                return result               # MUST return to propagate workflow output
            finally:
                cleanup_context()
        return wrapper()

Without 'return result', the workflow output will be lost (serialized_output will be null).

Metadata envelope approach:
------------------------------------------
This example uses the metadata envelope feature for production-ready context propagation.
Metadata is stored separately from the user payload and is transparent to user code.

Envelope structure (automatically handled by the runtime):
    {
        "__dapr_meta__": {
            "v": 1,
            "metadata": {"tenant": "acme", "request_id": "r-123"}
        },
        "__dapr_payload__": <original_input>
    }

Benefits:
 - User code never sees envelope structure (receives only the payload)
 - Metadata is durably persisted (survives replays, retries, continue-as-new)
 - Automatic propagation across workflow → activity → child workflow boundaries
 - String-only metadata enforces simple, serializable key-value structure
 - Context accessible to interceptors via request.metadata

Note: Scheduling/running requires a Dapr sidecar. This file focuses on the wiring pattern.
"""

from __future__ import annotations

import contextvars
import json
from dataclasses import replace
from typing import Any, Callable

from dapr.ext.workflow import (
    BaseClientInterceptor,
    BaseRuntimeInterceptor,
    BaseWorkflowOutboundInterceptor,
    CallActivityRequest,
    CallChildWorkflowRequest,
    DaprWorkflowClient,
    ExecuteActivityRequest,
    ExecuteWorkflowRequest,
    ScheduleWorkflowRequest,
    WorkflowRuntime,
)

# Context variable to carry request metadata across workflow/activity execution
_current_ctx: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    'wf_ctx', default=None
)


def set_ctx(ctx: dict[str, str] | None) -> None:
    """Set the current context (stored in contextvar)."""
    _current_ctx.set(ctx)


def get_ctx() -> dict[str, str] | None:
    """Get the current context from contextvar."""
    return _current_ctx.get()


class ContextClientInterceptor(BaseClientInterceptor):
    """Client interceptor that sets metadata when scheduling workflows.

    The metadata is automatically wrapped in an envelope by the runtime and
    propagated durably across workflow boundaries.
    """

    def schedule_new_workflow(
        self, request: ScheduleWorkflowRequest, nxt: Callable[[ScheduleWorkflowRequest], Any]
    ) -> Any:  # type: ignore[override]
        # Get current context and convert to string-only metadata
        ctx = get_ctx()
        metadata = ctx.copy() if ctx else {}

        print('[Client] Scheduling workflow with metadata:', metadata)

        # Set metadata on the request (runtime will wrap in envelope)
        return nxt(replace(request, metadata=metadata))


class ContextWorkflowOutboundInterceptor(BaseWorkflowOutboundInterceptor):
    """Workflow outbound interceptor that propagates metadata to activities and child workflows.

    The metadata is automatically wrapped in an envelope by the runtime.
    """

    def call_child_workflow(
        self, request: CallChildWorkflowRequest, nxt: Callable[[CallChildWorkflowRequest], Any]
    ) -> Any:
        # Get current context and convert to string-only metadata
        ctx = get_ctx()
        metadata = ctx.copy() if ctx else {}

        print('[Outbound] Calling child workflow with metadata:', metadata)

        # Use dataclasses.replace() to create a modified copy
        return nxt(replace(request, metadata=metadata))

    def call_activity(
        self, request: CallActivityRequest, nxt: Callable[[CallActivityRequest], Any]
    ) -> Any:
        # Get current context and convert to string-only metadata
        ctx = get_ctx()
        metadata = ctx.copy() if ctx else {}

        print(f'[Outbound] Calling activity {request.activity_name}')
        print(f'  -- input: {request.input}')
        print(f'  -- metadata: {metadata}')

        # Use dataclasses.replace() to create a modified copy
        return nxt(replace(request, metadata=metadata))


class ContextRuntimeInterceptor(BaseRuntimeInterceptor):
    """Runtime interceptor that restores context from metadata before execution.

    The runtime automatically unwraps the envelope and provides metadata via
    request.metadata. User code receives only the original payload via request.input.
    """

    def execute_workflow(
        self, request: ExecuteWorkflowRequest, nxt: Callable[[ExecuteWorkflowRequest], Any]
    ) -> Any:  # type: ignore[override]
        """
        IMPORTANT: Use wrapper pattern to keep context alive during generator execution.

        Calling nxt(request) returns a generator immediately; context must stay set
        while that generator executes (including during activity calls).
        """

        def wrapper():
            print('[Runtime] Executing workflow')
            print(f'  -- input (payload only): {request.input}')
            print(f'  -- metadata: {request.metadata}')

            # Restore context from metadata (automatically unwrapped by runtime)
            if request.metadata:
                set_ctx(request.metadata)

            try:
                gen = nxt(request)
                result = yield from gen  # Keep context alive while generator executes
                return result  # Must explicitly return the result from the inner generator
            finally:
                print('[Runtime] Clearing workflow context')
                set_ctx(None)

        return wrapper()

    def execute_activity(
        self, request: ExecuteActivityRequest, nxt: Callable[[ExecuteActivityRequest], Any]
    ) -> Any:  # type: ignore[override]
        """
        Restore context from metadata before activity execution.

        The runtime automatically unwraps the envelope and provides metadata via
        request.metadata. User code receives only the original payload.
        """
        # Restore context from metadata (automatically unwrapped by runtime)
        if request.metadata:
            set_ctx(request.metadata)

        try:
            return nxt(request)
        finally:
            set_ctx(None)


# Example workflow and activity demonstrating context access
def activity_log(ctx, data: dict[str, Any]) -> str:  # noqa: ANN001 (example)
    """
    Activity that accesses the restored context.

    The context was set in the runtime interceptor from metadata.
    The activity receives only the user payload (data), not the envelope.
    """
    current_context = get_ctx()

    if current_context is None:
        return dict(tenant='unknown', request_id='unknown', msg='no message', data=data)

    return dict(
        tenant=current_context.get('tenant', 'unknown'),
        request_id=current_context.get('request_id', 'unknown'),
        msg=data.get('msg', 'no message'),
        data=data,
    )


def workflow_example(ctx, wf_input: dict[str, Any]):  # noqa: ANN001 (example)
    """
    Example workflow that calls an activity.

    The workflow receives only the user payload (wf_input), not the envelope.
    The context is accessible via get_ctx() thanks to the runtime interceptor.
    """
    current_context = get_ctx()

    # Call activity - metadata will be propagated automatically via outbound interceptor
    y = yield ctx.call_activity(activity_log, input={'msg': 'hello from workflow'})

    return dict(result=y, context_was=json.dumps(current_context))


def wire_up() -> tuple[WorkflowRuntime, DaprWorkflowClient]:
    """Set up runtime and client with interceptors."""
    runtime = WorkflowRuntime(
        runtime_interceptors=[ContextRuntimeInterceptor()],
        workflow_outbound_interceptors=[ContextWorkflowOutboundInterceptor()],
    )
    client = DaprWorkflowClient(interceptors=[ContextClientInterceptor()])

    # Register workflow/activity
    runtime.register_workflow(workflow_example, name='example')
    runtime.register_activity(activity_log, name='activity_log')
    return runtime, client


if __name__ == '__main__':
    """
    Demonstrates metadata envelope approach:
    1. Client sets context in contextvar
    2. Client interceptor converts context to metadata
    3. Runtime wraps metadata in envelope: {"__dapr_meta__": {...}, "__dapr_payload__": {...}}
    4. Envelope is persisted durably in workflow state
    5. Runtime unwraps envelope before execution
    6. Runtime interceptor restores context from metadata
    7. User code receives only the payload, not the envelope
    """
    print('=' * 70)
    print('Metadata Envelope Context Propagation Example')
    print('=' * 70)

    wrt, client = wire_up()
    with wrt:
        # Set context - this will be converted to metadata by the client interceptor
        set_ctx({'tenant': 'acme-corp', 'request_id': 'req-12345'})

        # Schedule workflow with user payload (metadata is added by interceptor)
        instance_id = client.schedule_new_workflow(
            workflow_example, input={'operation': 'process_order', 'order_id': 999}
        )

        wf_state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)

    print('\n' + '=' * 70)
    print('Workflow Result:')
    print('=' * 70)
    print(f'Status: {wf_state.runtime_status}')
    print(f'Output: {wf_state.serialized_output}')
    print('=' * 70)
