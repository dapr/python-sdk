# -*- coding: utf-8 -*-

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

Example: Interceptors for context propagation with async workflows using metadata envelope.

This example demonstrates the RECOMMENDED approach for context propagation:
 - Use metadata envelope for durable, transparent context propagation
 - ClientInterceptor sets metadata when scheduling workflows
 - RuntimeInterceptor restores context from metadata before execution
 - WorkflowOutboundInterceptor propagates metadata to activities/child workflows
 - Use wrapper pattern with 'yield from' to keep context alive during execution

CRITICAL: Workflow interceptors MUST use the wrapper pattern and return the result:
    def execute_workflow(self, request, nxt):
        def wrapper():
            setup_context()
            try:
                gen = nxt(request)
                result = yield from gen  # Keep context alive during execution
                return result  # MUST return to propagate workflow output
            finally:
                cleanup_context()
        return wrapper()

Without 'return result', the workflow output will be lost (serialized_output will be null).

Metadata envelope approach (RECOMMENDED):
------------------------------------------
Metadata is stored separately from user payload and transparently wrapped/unwrapped by runtime.

Benefits:
 - User code receives only the payload (never sees envelope)
 - Durably persisted (survives replays, retries, continue-as-new)
 - Automatic propagation across workflow → activity → child workflow boundaries
 - String-only metadata enforces simple, serializable key-value structure
 - Context accessible to interceptors via request.metadata

Note: This requires a running Dapr sidecar to execute.
"""

from __future__ import annotations

import contextvars
from typing import Any, Callable

from dapr.ext.workflow import (
    AsyncWorkflowContext,
    BaseClientInterceptor,
    BaseRuntimeInterceptor,
    BaseWorkflowOutboundInterceptor,
    CallActivityRequest,
    CallChildWorkflowRequest,
    DaprWorkflowClient,
    ExecuteActivityRequest,
    ExecuteWorkflowRequest,
    ScheduleWorkflowRequest,
    WorkflowActivityContext,
    WorkflowRuntime,
)

# Context variable to carry request metadata across workflow/activity execution
_request_context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    'request_context', default=None
)


def set_request_context(ctx: dict[str, str] | None) -> None:
    """Set the current context (stored in contextvar)."""
    _request_context.set(ctx)


def get_request_context() -> dict[str, str] | None:
    """Get the current context from contextvar."""
    return _request_context.get()


class ContextClientInterceptor(BaseClientInterceptor):
    """Client interceptor that sets metadata when scheduling workflows.

    The metadata is automatically wrapped in an envelope by the runtime and
    propagated durably across workflow boundaries.
    """

    def schedule_new_workflow(
        self, request: ScheduleWorkflowRequest, nxt: Callable[[ScheduleWorkflowRequest], Any]
    ) -> Any:
        # Get current context and convert to string-only metadata
        ctx = get_request_context()
        metadata = ctx.copy() if ctx else {}

        print('[Client] Scheduling workflow with metadata:', metadata)

        # Set metadata on the request (runtime will wrap in envelope)
        modified_request = ScheduleWorkflowRequest(
            workflow_name=request.workflow_name,
            input=request.input,
            instance_id=request.instance_id,
            start_at=request.start_at,
            reuse_id_policy=request.reuse_id_policy,
            metadata=metadata,
        )
        return nxt(modified_request)


class ContextWorkflowOutboundInterceptor(BaseWorkflowOutboundInterceptor):
    """Workflow outbound interceptor that propagates metadata to activities and child workflows.

    The metadata is automatically wrapped in an envelope by the runtime.
    """

    def call_activity(
        self, request: CallActivityRequest, nxt: Callable[[CallActivityRequest], Any]
    ) -> Any:
        # Get current context and convert to string-only metadata
        ctx = get_request_context()
        metadata = ctx.copy() if ctx else {}

        return nxt(
            CallActivityRequest(
                activity_name=request.activity_name,
                input=request.input,
                retry_policy=request.retry_policy,
                workflow_ctx=request.workflow_ctx,
                metadata=metadata,
            )
        )

    def call_child_workflow(
        self, request: CallChildWorkflowRequest, nxt: Callable[[CallChildWorkflowRequest], Any]
    ) -> Any:
        # Get current context and convert to string-only metadata
        ctx = get_request_context()
        metadata = ctx.copy() if ctx else {}

        return nxt(
            CallChildWorkflowRequest(
                workflow_name=request.workflow_name,
                input=request.input,
                instance_id=request.instance_id,
                workflow_ctx=request.workflow_ctx,
                metadata=metadata,
            )
        )


class ContextRuntimeInterceptor(BaseRuntimeInterceptor):
    """Runtime interceptor that restores context from metadata before execution.

    The runtime automatically unwraps the envelope and provides metadata via
    request.metadata. User code receives only the original payload via request.input.
    """

    def execute_workflow(
        self, request: ExecuteWorkflowRequest, nxt: Callable[[ExecuteWorkflowRequest], Any]
    ) -> Any:
        """
        IMPORTANT: Use wrapper pattern to keep context alive during generator execution.

        Calling nxt(request) returns a generator immediately; context must stay set
        while that generator executes (including during activity calls and child workflows).
        """

        def wrapper():
            # Restore context from metadata (automatically unwrapped by runtime)
            if request.metadata:
                set_request_context(request.metadata)

            try:
                gen = nxt(request)
                result = yield from gen  # Keep context alive while generator executes
                return result  # Must explicitly return the result from the inner generator
            finally:
                set_request_context(None)

        return wrapper()

    def execute_activity(
        self, request: ExecuteActivityRequest, nxt: Callable[[ExecuteActivityRequest], Any]
    ) -> Any:
        """
        Restore context from metadata before activity execution.

        The runtime automatically unwraps the envelope and provides metadata via
        request.metadata. User code receives only the original payload.
        """
        # Restore context from metadata (automatically unwrapped by runtime)
        if request.metadata:
            set_request_context(request.metadata)

        try:
            return nxt(request)
        finally:
            set_request_context(None)


# Create runtime with interceptors
wfr = WorkflowRuntime(
    runtime_interceptors=[ContextRuntimeInterceptor()],
    workflow_outbound_interceptors=[ContextWorkflowOutboundInterceptor()],
)


@wfr.activity(name='process_data')
def process_data(ctx: WorkflowActivityContext, data: dict) -> dict:
    """
    Activity that accesses the restored context.

    The context was set in the runtime interceptor from metadata.
    The activity receives only the user payload (data), not the envelope.
    """
    request_ctx = get_request_context()

    if request_ctx is None:
        return {'tenant': 'unknown', 'request_id': 'unknown', 'message': 'no message', 'data': data}

    return {
        'tenant': request_ctx.get('tenant', 'unknown'),
        'request_id': request_ctx.get('request_id', 'unknown'),
        'message': data.get('message', 'no message'),
    }


@wfr.activity(name='aggregate_results')
def aggregate_results(ctx: WorkflowActivityContext, results: list) -> dict:
    """Activity that aggregates results for the same tenant in context."""
    request_ctx = get_request_context()
    tenant = request_ctx.get('tenant', 'unknown') if request_ctx else 'unknown'
    request_id = request_ctx.get('request_id', 'unknown') if request_ctx else 'unknown'
    tenant_results = [
        r['message'] for r in results if r['tenant'] == tenant and r['request_id'] == request_id
    ]

    return {
        'tenant': tenant,
        'request_id': request_id,
        'count': len(tenant_results),
        'results': tenant_results,
    }


@wfr.async_workflow(name='context_propagation_example')
async def context_propagation_workflow(ctx: AsyncWorkflowContext, input_data: dict) -> dict:
    """
    Workflow that demonstrates context propagation to activities.

    The workflow receives only the user payload (input_data), not the envelope.
    The context is accessible via get_request_context() thanks to the runtime interceptor.

    Activities are executed in parallel using when_all for better performance.
    """
    request_ctx = get_request_context()

    # map-reduce pattern

    # Create activity tasks (don't await yet) - metadata will be propagated automatically
    # Execute all activities in parallel and get results
    results = await ctx.when_all(
        [
            ctx.call_activity(process_data, input={'message': 'first task'}),
            ctx.call_activity(process_data, input={'message': 'second task'}),
            ctx.call_activity(process_data, input={'message': 'third task'}),
        ]
    )

    # Aggregate/reduce results
    final = await ctx.call_activity(aggregate_results, input=results)

    return {'final': final, 'context_was': request_ctx}


def main():
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
    print('Metadata Envelope Context Propagation Example (Async)')
    print('=' * 70)

    with wfr:
        # Create client with client interceptor
        client = DaprWorkflowClient(interceptors=[ContextClientInterceptor()])

        # Set context - this will be converted to metadata by the client interceptor
        set_request_context({'tenant': 'acme-corp', 'request_id': 'req-12345'})

        # Schedule workflow with user payload (metadata is added by interceptor)
        instance_id = 'context_example_async'
        client.schedule_new_workflow(
            workflow=context_propagation_workflow,
            input={'task': 'process_orders', 'order_id': 999},
            instance_id=instance_id,
        )

        wf_state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)

    print('\n' + '=' * 70)
    print('Workflow Result:')
    print('=' * 70)
    print(f'Status: {wf_state.runtime_status}')
    print(f'Output: {wf_state.serialized_output}')
    print('=' * 70)


if __name__ == '__main__':
    main()
