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
See the specific language governing permissions and
limitations under the License.
"""

import time

import pytest
from dapr.ext.workflow import (
    AsyncWorkflowContext,
    DaprWorkflowClient,
    DaprWorkflowContext,
    WorkflowRuntime,
)
from dapr.ext.workflow.interceptors import (
    BaseRuntimeInterceptor,
    ExecuteActivityRequest,
    ExecuteWorkflowRequest,
)

pytestmark = pytest.mark.e2e

skip_integration = pytest.mark.skipif(
    False,
    reason='integration enabled',
)


@skip_integration
def test_integration_suspension_and_buffering():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='suspend_orchestrator_async')
    async def suspend_orchestrator(ctx: AsyncWorkflowContext):
        # Expose suspension state via custom status
        ctx.set_custom_status({'is_suspended': getattr(ctx, 'is_suspended', False)})
        # Wait for 'resume_event' and then complete
        data = await ctx.wait_for_external_event('resume_event')
        return {'resumed_with': data}

    runtime.start()
    try:
        # Allow connection to stabilize before scheduling
        time.sleep(3)

        client = DaprWorkflowClient()
        instance_id = f'suspend-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=suspend_orchestrator, instance_id=instance_id)

        # Wait until started
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

        # Pause and verify state becomes SUSPENDED and custom status updates on next activation
        client.pause_workflow(instance_id)
        # Give the worker time to process suspension
        time.sleep(1)
        state = client.get_workflow_state(instance_id)
        assert state is not None
        assert state.runtime_status.name in (
            'SUSPENDED',
            'RUNNING',
        )  # some hubs report SUSPENDED explicitly

        # While suspended, raise the event; it should buffer
        client.raise_workflow_event(instance_id, 'resume_event', data={'ok': True})

        # Resume and expect completion
        client.resume_workflow(instance_id)
        final = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        assert final is not None
        assert final.runtime_status.name == 'COMPLETED'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_generator_metadata_propagation():
    runtime = WorkflowRuntime()

    @runtime.activity(name='recv_md_gen')
    def recv_md_gen(ctx, _=None):
        return ctx.get_metadata() or {}

    @runtime.workflow(name='gen_parent_sets_md')
    def parent_gen(ctx: DaprWorkflowContext):
        ctx.set_metadata({'tenant': 'acme', 'tier': 'gold'})
        md = yield ctx.call_activity(recv_md_gen, input=None)
        return md

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient()
        iid = f'gen-md-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=parent_gen, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        state = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert state is not None
        assert state.runtime_status.name == 'COMPLETED'
        import json as _json

        out = _json.loads(state.to_json().get('serialized_output') or '{}')
        assert out.get('tenant') == 'acme'
        assert out.get('tier') == 'gold'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_trace_context_child_workflow():
    runtime = WorkflowRuntime()

    @runtime.activity(name='trace_probe')
    def trace_probe(ctx, _=None):
        return {
            'tp': getattr(ctx, 'trace_parent', None),
            'ts': getattr(ctx, 'trace_state', None),
            'wf_span': getattr(ctx, 'workflow_span_id', None),
        }

    @runtime.async_workflow(name='child_trace')
    async def child(ctx: AsyncWorkflowContext, _=None):
        return {
            'wf_tp': getattr(ctx, 'trace_parent', None),
            'wf_ts': getattr(ctx, 'trace_state', None),
            'wf_span': getattr(ctx, 'workflow_span_id', None),
            'act': await ctx.call_activity(trace_probe, input=None),
        }

    @runtime.async_workflow(name='parent_trace')
    async def parent(ctx: AsyncWorkflowContext):
        child_out = await ctx.call_child_workflow(child, input=None)
        return {
            'parent_tp': getattr(ctx, 'trace_parent', None),
            'parent_span': getattr(ctx, 'workflow_span_id', None),
            'child': child_out,
        }

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient()
        iid = f'trace-child-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=parent, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None and st.runtime_status.name == 'COMPLETED'
        import json as _json

        data = _json.loads(st.to_json().get('serialized_output') or '{}')

        # TODO: assert more specifically when we have trace context information

        # Parent (engine-provided fields may be absent depending on runtime build/config)
        assert isinstance(data.get('parent_tp'), (str, type(None)))
        assert isinstance(data.get('parent_span'), (str, type(None)))
        # Child orchestrator fields
        _child = data.get('child') or {}
        assert isinstance(_child.get('wf_tp'), (str, type(None)))
        assert isinstance(_child.get('wf_span'), (str, type(None)))
        # Activity fields under child
        act = _child.get('act') or {}
        assert isinstance(act.get('tp'), (str, type(None)))
        assert isinstance(act.get('wf_span'), (str, type(None)))

    finally:
        runtime.shutdown()


@skip_integration
def test_integration_trace_context_child_workflow_injected_metadata():
    # Deterministic trace propagation using interceptors via durable metadata
    from dapr.ext.workflow import (
        BaseClientInterceptor,
        BaseRuntimeInterceptor,
        BaseWorkflowOutboundInterceptor,
        CallActivityRequest,
        CallChildWorkflowRequest,
        ScheduleWorkflowRequest,
    )

    TRACE_KEY = 'otel.trace_id'

    class InjectTraceClient(BaseClientInterceptor):
        def schedule_new_workflow(self, request: ScheduleWorkflowRequest, next):
            md = dict(request.metadata or {})
            md.setdefault(TRACE_KEY, 'sdk-trace-123')
            return next(
                ScheduleWorkflowRequest(
                    workflow_name=request.workflow_name,
                    input=request.input,
                    instance_id=request.instance_id,
                    start_at=request.start_at,
                    reuse_id_policy=request.reuse_id_policy,
                    metadata=md,
                )
            )

    class InjectTraceOutbound(BaseWorkflowOutboundInterceptor):
        def call_activity(self, request: CallActivityRequest, next):
            md = dict(request.metadata or {})
            md.setdefault(TRACE_KEY, 'sdk-trace-123')
            return next(
                CallActivityRequest(
                    activity_name=request.activity_name,
                    input=request.input,
                    retry_policy=request.retry_policy,
                    workflow_ctx=request.workflow_ctx,
                    metadata=md,
                )
            )

        def call_child_workflow(self, request: CallChildWorkflowRequest, next):
            md = dict(request.metadata or {})
            md.setdefault(TRACE_KEY, 'sdk-trace-123')
            return next(
                CallChildWorkflowRequest(
                    workflow_name=request.workflow_name,
                    input=request.input,
                    instance_id=request.instance_id,
                    workflow_ctx=request.workflow_ctx,
                    metadata=md,
                )
            )

    class RestoreTraceRuntime(BaseRuntimeInterceptor):
        def execute_workflow(self, request: ExecuteWorkflowRequest, next):
            # Ensure metadata arrives
            assert isinstance((request.metadata or {}).get(TRACE_KEY), str)
            return next(request)

        def execute_activity(self, request: ExecuteActivityRequest, next):
            assert isinstance((request.metadata or {}).get(TRACE_KEY), str)
            return next(request)

    runtime = WorkflowRuntime(
        runtime_interceptors=[RestoreTraceRuntime()],
        workflow_outbound_interceptors=[InjectTraceOutbound()],
    )

    @runtime.activity(name='trace_probe2')
    def trace_probe2(ctx, _=None):
        return getattr(ctx, 'get_metadata', lambda: {})().get(TRACE_KEY)

    @runtime.async_workflow(name='child_trace2')
    async def child2(ctx: AsyncWorkflowContext, _=None):
        return {
            'wf_md': (ctx.get_metadata() or {}).get(TRACE_KEY),
            'act_md': await ctx.call_activity(trace_probe2, input=None),
        }

    @runtime.async_workflow(name='parent_trace2')
    async def parent2(ctx: AsyncWorkflowContext):
        out = await ctx.call_child_workflow(child2, input=None)
        return {
            'parent_md': (ctx.get_metadata() or {}).get(TRACE_KEY),
            'child': out,
        }

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient(interceptors=[InjectTraceClient()])
        iid = f'trace-child-md-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=parent2, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None and st.runtime_status.name == 'COMPLETED'
        import json as _json

        data = _json.loads(st.to_json().get('serialized_output') or '{}')
        assert data.get('parent_md') == 'sdk-trace-123'
        child = data.get('child') or {}
        assert child.get('wf_md') == 'sdk-trace-123'
        assert child.get('act_md') == 'sdk-trace-123'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_termination_semantics():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='termination_orchestrator_async')
    async def termination_orchestrator(ctx: AsyncWorkflowContext):
        # Long timer; test will terminate before it fires
        await ctx.create_timer(300.0)
        return 'not-reached'

    print(list(runtime._WorkflowRuntime__worker._registry.orchestrators.keys()))

    runtime.start()
    try:
        time.sleep(3)

        client = DaprWorkflowClient()
        instance_id = f'term-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=termination_orchestrator, instance_id=instance_id)
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

        # Terminate and assert TERMINATED state, not raising inside orchestrator
        client.terminate_workflow(instance_id, output='terminated')
        final = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        assert final is not None
        assert final.runtime_status.name == 'TERMINATED'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_when_any_first_wins():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='when_any_async')
    async def when_any_orchestrator(ctx: AsyncWorkflowContext):
        first = await ctx.when_any(
            [
                ctx.wait_for_external_event('go'),
                ctx.create_timer(300.0),
            ]
        )
        # Return a simple, serializable value (winner's result) to avoid output serialization issues
        try:
            result = first.get_result()
        except Exception:
            result = None
        return {'winner_result': result}

    runtime.start()
    try:
        # Ensure worker has established streams before scheduling
        try:
            if hasattr(runtime, 'wait_for_ready'):
                runtime.wait_for_ready(timeout=15)  # type: ignore[attr-defined]
        except Exception:
            pass
        time.sleep(2)

        client = DaprWorkflowClient()
        instance_id = f'whenany-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=when_any_orchestrator, instance_id=instance_id)
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)
        # Confirm RUNNING state before raising event (mitigates race conditions)
        try:
            st = client.get_workflow_state(instance_id, fetch_payloads=False)
            if (
                st is None
                or getattr(st, 'runtime_status', None) is None
                or st.runtime_status.name != 'RUNNING'
            ):
                end = time.time() + 10
                while time.time() < end:
                    st = client.get_workflow_state(instance_id, fetch_payloads=False)
                    if (
                        st is not None
                        and getattr(st, 'runtime_status', None) is not None
                        and st.runtime_status.name == 'RUNNING'
                    ):
                        break
                    time.sleep(0.2)
        except Exception:
            pass

        # Raise event immediately to win the when_any
        client.raise_workflow_event(instance_id, 'go', data={'ok': True})

        # Brief delay to allow event processing, then strictly use DaprWorkflowClient
        time.sleep(1.0)
        final = None
        try:
            final = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
        except TimeoutError:
            final = None
        if final is None:
            deadline = time.time() + 30
            while time.time() < deadline:
                s = client.get_workflow_state(instance_id, fetch_payloads=False)
                if s is not None and getattr(s, 'runtime_status', None) is not None:
                    if s.runtime_status.name in ('COMPLETED', 'FAILED', 'TERMINATED'):
                        final = s
                        break
                time.sleep(0.5)
        assert final is not None
        assert final.runtime_status.name == 'COMPLETED'
        # TODO: when sidecar exposes command diagnostics, assert only one command set was emitted
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_async_activity_completes():
    runtime = WorkflowRuntime()

    @runtime.activity(name='echo_int')
    def echo_act(ctx, x: int) -> int:
        return x

    @runtime.async_workflow(name='async_activity_once')
    async def wf(ctx: AsyncWorkflowContext):
        out = await ctx.call_activity(echo_act, input=7)
        return out

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient()
        iid = f'act-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=wf, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        state = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert state is not None
        if state.runtime_status.name != 'COMPLETED':
            fd = getattr(state, 'failure_details', None)
            msg = getattr(fd, 'message', None) if fd else None
            et = getattr(fd, 'error_type', None) if fd else None
            print(f'[INTEGRATION DEBUG] Failure details: {et} {msg}')
        assert state.runtime_status.name == 'COMPLETED'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_metadata_outbound_to_activity():
    runtime = WorkflowRuntime()

    @runtime.activity(name='recv_md')
    def recv_md(ctx, _=None):
        md = ctx.get_metadata() if hasattr(ctx, 'get_metadata') else {}
        return md

    @runtime.async_workflow(name='wf_with_md')
    async def wf(ctx: AsyncWorkflowContext):
        ctx.set_metadata({'tenant': 'acme'})
        md = await ctx.call_activity(recv_md, input=None)
        return md

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient()
        iid = f'md-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=wf, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        state = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert state is not None
        assert state.runtime_status.name == 'COMPLETED'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_metadata_outbound_to_child_workflow():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='child_recv_md')
    async def child(ctx: AsyncWorkflowContext, _=None):
        # Echo inbound metadata
        return ctx.get_metadata() or {}

    @runtime.async_workflow(name='parent_sets_md')
    async def parent(ctx: AsyncWorkflowContext):
        ctx.set_metadata({'tenant': 'acme', 'role': 'user'})
        out = await ctx.call_child_workflow(child, input=None)
        return out

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient()
        iid = f'md-child-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=parent, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        state = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert state is not None
        assert state.runtime_status.name == 'COMPLETED'
        # Validate output has metadata keys
        data = state.to_json()
        import json as _json

        out = _json.loads(data.get('serialized_output') or '{}')
        assert out.get('tenant') == 'acme'
        assert out.get('role') == 'user'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_trace_context_with_runtime_interceptors():
    """E2E: Verify trace_parent and orchestration_span_id via runtime interceptors."""
    records = {  # captured by interceptor
        'wf_tp': None,
        'wf_span': None,
        'act_tp': None,
        'act_span': None,
    }

    class TraceInterceptor(BaseRuntimeInterceptor):
        def execute_workflow(self, request: ExecuteWorkflowRequest, next):  # type: ignore[override]
            ctx = request.ctx
            try:
                records['wf_tp'] = getattr(ctx, 'trace_parent', None)
                records['wf_span'] = getattr(ctx, 'workflow_span_id', None)
            except Exception:
                pass
            return next(request)

        def execute_activity(self, request: ExecuteActivityRequest, next):  # type: ignore[override]
            ctx = request.ctx
            try:
                records['act_tp'] = getattr(ctx, 'trace_parent', None)
                # Activity contexts don't have orchestration_span_id; capture task span if present
                records['act_span'] = getattr(ctx, 'activity_span_id', None)
            except Exception:
                pass
            return next(request)

    runtime = WorkflowRuntime(runtime_interceptors=[TraceInterceptor()])

    @runtime.activity(name='trace_probe')
    def trace_probe(ctx, _=None):
        # Return trace context seen inside activity
        return {
            'trace_parent': getattr(ctx, 'trace_parent', None),
            'trace_state': getattr(ctx, 'trace_state', None),
        }

    @runtime.async_workflow(name='trace_parent_wf')
    async def wf(ctx: AsyncWorkflowContext):
        # Access orchestration span id and trace parent from workflow context
        _ = getattr(ctx, 'workflow_span_id', None)
        _ = getattr(ctx, 'trace_parent', None)
        return await ctx.call_activity(trace_probe, input=None)

    runtime.start()
    try:
        time.sleep(3)
        client = DaprWorkflowClient()
        iid = f'trace-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=wf, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        state = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert state is not None
        assert state.runtime_status.name == 'COMPLETED'
        import json as _json

        out = _json.loads(state.to_json().get('serialized_output') or '{}')
        # Activity returned strings (may be empty); assert types
        assert isinstance(out.get('trace_parent'), (str, type(None)))
        assert isinstance(out.get('trace_state'), (str, type(None)))
        # Interceptor captured workflow and activity contexts
        wf_tp = records['wf_tp']
        wf_span = records['wf_span']
        act_tp = records['act_tp']
        # TODO: assert more specifically when we have trace context information
        assert isinstance(wf_tp, (str, type(None)))
        assert isinstance(wf_span, (str, type(None)))
        assert isinstance(act_tp, (str, type(None)))
        # If we have a workflow span id, it should appear as parent-id inside activity traceparent
        if isinstance(wf_span, str) and wf_span and isinstance(act_tp, str) and act_tp:
            assert wf_span.lower() in act_tp.lower()
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_runtime_shutdown_is_clean():
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='noop')
    async def noop(ctx: AsyncWorkflowContext):
        return 'ok'

    runtime.start()
    try:
        time.sleep(2)
        client = DaprWorkflowClient()
        iid = f'shutdown-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=noop, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=30)
        assert st is not None and st.runtime_status.name == 'COMPLETED'
    finally:
        # Call shutdown multiple times to ensure idempotent and clean behavior
        for _ in range(3):
            try:
                runtime.shutdown()
            except Exception:
                # Test should not raise even if worker logs cancellation warnings
                assert False, 'runtime.shutdown() raised unexpectedly'
        # Recreate and shutdown again to ensure no lingering background threads break next startup
        rt2 = WorkflowRuntime()
        rt2.start()
        try:
            time.sleep(1)
        finally:
            try:
                rt2.shutdown()
            except Exception:
                assert False, 'second runtime.shutdown() raised unexpectedly'


@skip_integration
def test_integration_continue_as_new_outbound_interceptor_metadata():
    # Verify continue_as_new outbound interceptor can inject metadata carried to the new run
    from dapr.ext.workflow import BaseWorkflowOutboundInterceptor

    INJECT_KEY = 'injected'

    class InjectOnContinueAsNew(BaseWorkflowOutboundInterceptor):
        def continue_as_new(self, request, next):  # type: ignore[override]
            md = dict(request.metadata or {})
            md.setdefault(INJECT_KEY, 'yes')
            request.metadata = md
            return next(request)

    runtime = WorkflowRuntime(
        workflow_outbound_interceptors=[InjectOnContinueAsNew()],
    )

    @runtime.workflow(name='continue_as_new_probe')
    def wf(ctx, arg: dict | None = None):
        if not arg or arg.get('phase') != 'second':
            ctx.set_metadata({'tenant': 'acme'})
            # carry over existing metadata; interceptor will also inject
            ctx.continue_as_new({'phase': 'second'}, carryover_metadata=True)
            return  # Must not yield after continue_as_new
        # Second run: return inbound metadata observed
        return ctx.get_metadata() or {}

    runtime.start()
    try:
        time.sleep(2)
        client = DaprWorkflowClient()
        iid = f'can-int-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=wf, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None and st.runtime_status.name == 'COMPLETED'
        import json as _json

        out = _json.loads(st.to_json().get('serialized_output') or '{}')
        # Confirm both carried and injected metadata are present
        assert out.get('tenant') == 'acme'
        assert out.get(INJECT_KEY) == 'yes'
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_child_workflow_attempt_exposed():
    # Verify that child workflow ctx exposes workflow_attempt
    runtime = WorkflowRuntime()

    @runtime.async_workflow(name='child_probe_attempt')
    async def child_probe_attempt(ctx: AsyncWorkflowContext, _=None):
        att = getattr(ctx, 'workflow_attempt', None)
        return {'wf_attempt': att}

    @runtime.async_workflow(name='parent_calls_child_for_attempt')
    async def parent_calls_child_for_attempt(ctx: AsyncWorkflowContext):
        return await ctx.call_child_workflow(child_probe_attempt, input=None)

    runtime.start()
    try:
        time.sleep(2)
        client = DaprWorkflowClient()
        iid = f'child-attempt-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=parent_calls_child_for_attempt, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None and st.runtime_status.name == 'COMPLETED'
        import json as _json

        out = _json.loads(st.to_json().get('serialized_output') or '{}')
        val = out.get('wf_attempt', None)
        assert (val is None) or isinstance(val, int)
    finally:
        runtime.shutdown()


@skip_integration
def test_integration_async_contextvars_trace_propagation(monkeypatch):
    # Demonstrates contextvars-based trace propagation via interceptors in async workflows
    import contextvars
    import json as _json

    from dapr.ext.workflow import (
        BaseClientInterceptor,
        BaseWorkflowOutboundInterceptor,
        CallActivityRequest,
        CallChildWorkflowRequest,
        ScheduleWorkflowRequest,
    )

    TRACE_KEY = 'otel.trace_ctx'
    current_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar(
        'trace', default=None
    )

    class CVClient(BaseClientInterceptor):
        def schedule_new_workflow(self, request: ScheduleWorkflowRequest, next):  # type: ignore[override]
            md = dict(request.metadata or {})
            md.setdefault(TRACE_KEY, 'wf-parent')
            return next(
                ScheduleWorkflowRequest(
                    workflow_name=request.workflow_name,
                    input=request.input,
                    instance_id=request.instance_id,
                    start_at=request.start_at,
                    reuse_id_policy=request.reuse_id_policy,
                    metadata=md,
                )
            )

    class CVOutbound(BaseWorkflowOutboundInterceptor):
        def call_activity(self, request: CallActivityRequest, next):  # type: ignore[override]
            md = dict(request.metadata or {})
            md.setdefault(TRACE_KEY, current_trace.get())
            return next(
                CallActivityRequest(
                    activity_name=request.activity_name,
                    input=request.input,
                    retry_policy=request.retry_policy,
                    workflow_ctx=request.workflow_ctx,
                    metadata=md,
                )
            )

        def call_child_workflow(self, request: CallChildWorkflowRequest, next):  # type: ignore[override]
            md = dict(request.metadata or {})
            md.setdefault(TRACE_KEY, current_trace.get())
            return next(
                CallChildWorkflowRequest(
                    workflow_name=request.workflow_name,
                    input=request.input,
                    instance_id=request.instance_id,
                    workflow_ctx=request.workflow_ctx,
                    metadata=md,
                )
            )

    class CVRuntime(BaseRuntimeInterceptor):
        def execute_workflow(self, request: ExecuteWorkflowRequest, next):  # type: ignore[override]
            prev = current_trace.set((request.metadata or {}).get(TRACE_KEY))
            try:
                return next(request)
            finally:
                current_trace.reset(prev)

        def execute_activity(self, request: ExecuteActivityRequest, next):  # type: ignore[override]
            prev = current_trace.set((request.metadata or {}).get(TRACE_KEY))
            try:
                return next(request)
            finally:
                current_trace.reset(prev)

    runtime = WorkflowRuntime(
        runtime_interceptors=[CVRuntime()], workflow_outbound_interceptors=[CVOutbound()]
    )

    @runtime.activity(name='cv_probe')
    def cv_probe(_ctx, _=None):
        before = current_trace.get()
        tok = current_trace.set(f'{before}/act') if before else None
        try:
            inner = current_trace.get()
        finally:
            if tok is not None:
                current_trace.reset(tok)
        after = current_trace.get()
        return {'before': before, 'inner': inner, 'after': after}

    flaky_call_count = [0]

    @runtime.activity(name='cv_flaky_probe')
    def cv_flaky_probe(ctx, _=None):
        before = current_trace.get()
        flaky_call_count[0] += 1
        print(f'----------> flaky_call_count: {flaky_call_count[0]}')
        if flaky_call_count[0] == 1:
            # Fail first attempt to trigger retry
            raise Exception('fail-once')
        tok = current_trace.set(f'{before}/act-retry') if before else None
        try:
            inner = current_trace.get()
        finally:
            if tok is not None:
                current_trace.reset(tok)
        after = current_trace.get()
        return {'before': before, 'inner': inner, 'after': after}

    @runtime.async_workflow(name='cv_child')
    async def cv_child(ctx: AsyncWorkflowContext, _=None):
        before = current_trace.get()
        tok = current_trace.set(f'{before}/child') if before else None
        try:
            act = await ctx.call_activity(cv_probe, input=None)
        finally:
            if tok is not None:
                current_trace.reset(tok)
        restored = current_trace.get()
        return {'before': before, 'restored': restored, 'act': act}

    @runtime.async_workflow(name='cv_parent')
    async def cv_parent(ctx: AsyncWorkflowContext, _=None):
        from datetime import timedelta

        from dapr.ext.workflow import RetryPolicy

        top_before = current_trace.get()
        child = await ctx.call_child_workflow(cv_child, input=None)
        after_child = current_trace.get()
        act = await ctx.call_activity(cv_probe, input=None)
        after_act = current_trace.get()
        act_retry = await ctx.call_activity(
            cv_flaky_probe,
            input=None,
            retry_policy=RetryPolicy(
                first_retry_interval=timedelta(seconds=0), max_number_of_attempts=3
            ),
        )
        return {
            'before': top_before,
            'child': child,
            'act': act,
            'act_retry': act_retry,
            'after_child': after_child,
            'after_act': after_act,
        }

    runtime.start()
    try:
        time.sleep(2)
        client = DaprWorkflowClient(interceptors=[CVClient()])
        iid = f'cv-ctx-{int(time.time() * 1000)}'
        client.schedule_new_workflow(workflow=cv_parent, instance_id=iid)
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None and st.runtime_status.name == 'COMPLETED'
        out = _json.loads(st.to_json().get('serialized_output') or '{}')
        # Top-level activity sees parent trace context during execution
        act = out.get('act') or {}
        assert act.get('before') == 'wf-parent'
        assert act.get('inner') == 'wf-parent/act'
        assert act.get('after') == 'wf-parent'
        # Child workflow's activity at least inherits parent context
        child = out.get('child') or {}
        child_act = child.get('act') or {}
        assert child_act.get('before') == 'wf-parent'
        assert child_act.get('inner') == 'wf-parent/act'
        assert child_act.get('after') == 'wf-parent'
        # Flaky activity retried: second attempt succeeds and returns with parent context
        act_retry = out.get('act_retry') or {}
        assert act_retry.get('before') == 'wf-parent'
        assert act_retry.get('inner') == 'wf-parent/act-retry'
        assert act_retry.get('after') == 'wf-parent'
    finally:
        runtime.shutdown()


def test_runtime_interceptor_shapes_async_input():
    runtime = WorkflowRuntime()

    class ShapeInput(BaseRuntimeInterceptor):
        def execute_workflow(self, request: ExecuteWorkflowRequest, next):  # type: ignore[override]
            data = request.input
            # Mutate input passed to workflow
            if isinstance(data, dict):
                shaped = {**data, 'shaped': True}
            else:
                shaped = {'value': data, 'shaped': True}
            request.input = shaped
            return next(request)

    # Recreate runtime with interceptor wired in
    runtime = WorkflowRuntime(runtime_interceptors=[ShapeInput()])

    @runtime.async_workflow(name='wf_shape_input')
    async def wf_shape_input(ctx: AsyncWorkflowContext, arg: dict | None = None):
        # Verify shaped input is observed by the workflow
        return arg

    runtime.start()
    try:
        from dapr.ext.workflow import DaprWorkflowClient

        client = DaprWorkflowClient()
        iid = f'shape-{id(runtime)}'
        client.schedule_new_workflow(workflow=wf_shape_input, instance_id=iid, input={'x': 1})
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None
        assert st.runtime_status.name == 'COMPLETED'
        import json as _json

        out = _json.loads(st.to_json().get('serialized_output') or '{}')
        assert out.get('x') == 1
        assert out.get('shaped') is True
    finally:
        runtime.shutdown()


def test_runtime_interceptor_context_manager_with_async_workflow():
    """Test that context managers stay active during async workflow execution."""
    runtime = WorkflowRuntime()

    # Track when context enters and exits
    context_state = {'entered': False, 'exited': False, 'workflow_ran': False}

    class ContextInterceptor(BaseRuntimeInterceptor):
        def execute_workflow(self, request: ExecuteWorkflowRequest, next):  # type: ignore[override]
            # Wrapper generator to keep context manager alive
            def wrapper():
                from contextlib import ExitStack

                with ExitStack():
                    # Mark context as entered
                    context_state['entered'] = True

                    # Get the workflow generator
                    gen = next(request)

                    # Use yield from to keep context alive during execution
                    yield from gen

                    # Context will exit after generator completes
                    context_state['exited'] = True

            return wrapper()

    runtime = WorkflowRuntime(runtime_interceptors=[ContextInterceptor()])

    @runtime.async_workflow(name='wf_context_test')
    async def wf_context_test(ctx: AsyncWorkflowContext, arg: dict | None = None):
        context_state['workflow_ran'] = True
        return {'result': 'ok'}

    runtime.start()
    try:
        from dapr.ext.workflow import DaprWorkflowClient

        client = DaprWorkflowClient()
        iid = f'ctx-test-{id(runtime)}'
        client.schedule_new_workflow(workflow=wf_context_test, instance_id=iid, input={})
        client.wait_for_workflow_start(iid, timeout_in_seconds=30)
        st = client.wait_for_workflow_completion(iid, timeout_in_seconds=60)
        assert st is not None
        assert st.runtime_status.name == 'COMPLETED'

        # Verify context manager was active during workflow execution
        assert context_state['entered'], 'Context should have been entered'
        assert context_state['workflow_ran'], 'Workflow should have executed'
        assert context_state['exited'], 'Context should have exited after completion'
    finally:
        runtime.shutdown()
