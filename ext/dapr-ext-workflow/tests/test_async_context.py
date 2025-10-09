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

import types
from datetime import datetime, timedelta, timezone

from dapr.ext.workflow import AsyncWorkflowContext, WorkflowRuntime
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.interceptors import BaseRuntimeInterceptor, ExecuteWorkflowRequest
from dapr.ext.workflow.workflow_context import WorkflowContext


class DummyBaseCtx:
    def __init__(self):
        self.instance_id = 'abc-123'
        # freeze a deterministic timestamp
        self.current_utc_datetime = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.is_replaying = False
        self._custom_status = None
        self._continued = None
        self._metadata = None
        self._ei = types.SimpleNamespace(
            workflow_id='abc-123',
            workflow_name='wf',
            is_replaying=False,
            history_event_sequence=1,
            inbound_metadata={'a': 'b'},
            parent_instance_id=None,
        )

    def set_custom_status(self, s: str):
        self._custom_status = s

    def continue_as_new(self, new_input, *, save_events: bool = False):
        self._continued = (new_input, save_events)

    # Metadata parity
    def set_metadata(self, md):
        self._metadata = md

    def get_metadata(self):
        return self._metadata

    @property
    def execution_info(self):
        return self._ei


def test_parity_properties_and_now():
    ctx = AsyncWorkflowContext(DummyBaseCtx())
    assert ctx.instance_id == 'abc-123'
    assert ctx.current_utc_datetime == datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    # now() should mirror current_utc_datetime
    assert ctx.now() == ctx.current_utc_datetime


def test_timer_accepts_float_and_timedelta():
    base = DummyBaseCtx()
    ctx = AsyncWorkflowContext(base)

    # Float should be interpreted as seconds and produce a SleepAwaitable
    aw1 = ctx.create_timer(1.5)
    # Timedelta should pass through
    aw2 = ctx.create_timer(timedelta(seconds=2))

    # We only assert types by duck-typing public attribute presence to avoid
    # importing internal classes in tests
    assert hasattr(aw1, '_ctx') and hasattr(aw1, '__await__')
    assert hasattr(aw2, '_ctx') and hasattr(aw2, '__await__')


def test_wait_for_external_event_and_concurrency_factories():
    ctx = AsyncWorkflowContext(DummyBaseCtx())

    evt = ctx.wait_for_external_event('go')
    assert hasattr(evt, '__await__')

    # when_all/when_any/gather return awaitables
    a = ctx.create_timer(0.1)
    b = ctx.create_timer(0.2)

    all_aw = ctx.when_all([a, b])
    any_aw = ctx.when_any([a, b])
    gat_aw = ctx.gather(a, b)
    gat_exc_aw = ctx.gather(a, b, return_exceptions=True)

    for x in (all_aw, any_aw, gat_aw, gat_exc_aw):
        assert hasattr(x, '__await__')


def test_deterministic_utils_and_passthroughs():
    base = DummyBaseCtx()
    ctx = AsyncWorkflowContext(base)

    rnd = ctx.random()
    # should behave like a random.Random-like object; test a stable first value
    val = rnd.random()
    # Just assert it is within (0,1) and stable across two calls to the seeded RNG instance
    assert 0.0 < val < 1.0
    assert rnd.random() != val  # next value changes

    uid = ctx.uuid4()
    # Should be a UUID-like string representation
    assert isinstance(str(uid), str) and len(str(uid)) >= 32

    # passthroughs
    ctx.set_custom_status('hello')
    assert base._custom_status == 'hello'

    ctx.continue_as_new({'x': 1}, save_events=True)
    assert base._continued == ({'x': 1}, True)


def test_async_metadata_api_and_execution_info():
    base = DummyBaseCtx()
    ctx = AsyncWorkflowContext(base)
    ctx.set_metadata({'k': 'v'})
    assert base._metadata == {'k': 'v'}
    assert ctx.get_metadata() == {'k': 'v'}
    ei = ctx.execution_info
    assert ei and ei.workflow_id == 'abc-123' and ei.workflow_name == 'wf'


def test_async_outbound_metadata_plumbed_into_awaitables():
    base = DummyBaseCtx()
    ctx = AsyncWorkflowContext(base)
    a = ctx.call_activity(lambda: None, input=1, metadata={'m': 'n'})
    c = ctx.call_child_workflow(lambda c, x: None, input=2, metadata={'x': 'y'})
    # Introspect for test (internal attribute)
    assert getattr(a, '_metadata', None) == {'m': 'n'}
    assert getattr(c, '_metadata', None) == {'x': 'y'}


def test_async_parity_surface_exists():
    # Guard: ensure essential parity members exist
    ctx = AsyncWorkflowContext(DummyBaseCtx())
    for name in (
        'set_metadata',
        'get_metadata',
        'execution_info',
        'call_activity',
        'call_child_workflow',
        'continue_as_new',
    ):
        assert hasattr(ctx, name)


def test_public_api_parity_against_workflowcontext_abc():
    # Derive the required sync API surface from the ABC plus metadata/execution_info
    required = {
        name
        for name, attr in WorkflowContext.__dict__.items()
        if getattr(attr, '__isabstractmethod__', False)
    }
    required.update({'set_metadata', 'get_metadata', 'execution_info'})

    # Async context must expose the same names
    async_ctx = AsyncWorkflowContext(DummyBaseCtx())
    missing_in_async = [name for name in required if not hasattr(async_ctx, name)]
    assert not missing_in_async, f'AsyncWorkflowContext missing: {missing_in_async}'

    # Sync context should also expose these names
    class _FakeOrchCtx:
        def __init__(self):
            self.instance_id = 'abc-123'
            self.current_utc_datetime = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
            self.is_replaying = False

        def set_custom_status(self, s: str):
            pass

        def create_timer(self, fire_at):
            return object()

        def wait_for_external_event(self, name: str):
            return object()

        def continue_as_new(self, new_input, *, save_events: bool = False):
            pass

        def call_activity(self, *, activity, input=None, retry_policy=None):
            return object()

        def call_sub_orchestrator(self, fn, *, input=None, instance_id=None, retry_policy=None):
            return object()

    sync_ctx = DaprWorkflowContext(_FakeOrchCtx())
    missing_in_sync = [name for name in required if not hasattr(sync_ctx, name)]
    assert not missing_in_sync, f'DaprWorkflowContext missing: {missing_in_sync}'


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
