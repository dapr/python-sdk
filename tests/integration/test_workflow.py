import uuid
from typing import Generator

import pytest
from dapr.ext.workflow import (
    DaprWorkflowClient,
    DaprWorkflowContext,
    WorkflowActivityContext,
    WorkflowRuntime,
)


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    return dapr_env.start_sidecar(app_id='test-workflow')


@pytest.fixture(scope='module')
def runtime(sidecar) -> Generator[WorkflowRuntime, None, None]:
    wfr = WorkflowRuntime()

    @wfr.activity(name='double_it')
    def double_it(ctx: WorkflowActivityContext, value: int) -> int:
        return value * 2

    @wfr.activity(name='add_one')
    def add_one(ctx: WorkflowActivityContext, value: int) -> int:
        return value + 1

    @wfr.workflow(name='chain_math_wf')
    def chain_math_wf(ctx: DaprWorkflowContext, wf_input: int):
        doubled = yield ctx.call_activity(double_it, input=wf_input)
        final = yield ctx.call_activity(add_one, input=doubled)
        return final

    @wfr.workflow(name='echo_input_wf')
    def echo_input_wf(ctx: DaprWorkflowContext, wf_input: str):
        return wf_input

    @wfr.workflow(name='external_event_wf')
    def external_event_wf(ctx: DaprWorkflowContext, _):
        event_payload = yield ctx.wait_for_external_event('go')
        return event_payload

    wfr.start()
    try:
        yield wfr
    finally:
        wfr.shutdown()


@pytest.fixture(scope='module')
def wf_client(runtime) -> Generator[DaprWorkflowClient, None, None]:
    wfc = DaprWorkflowClient()
    try:
        yield wfc
    finally:
        wfc.close()


def _instance_id(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


def test_activity_chain_returns_final_output(wf_client):
    instance_id = wf_client.schedule_new_workflow(
        workflow='chain_math_wf', input=5, instance_id=_instance_id('chain')
    )

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    wf_client.purge_workflow(instance_id)

    assert state is not None
    assert state.runtime_status.name == 'COMPLETED'
    assert state.serialized_output == '11'


def test_workflow_echoes_input(wf_client):
    instance_id = wf_client.schedule_new_workflow(
        workflow='echo_input_wf', input='ping', instance_id=_instance_id('echo')
    )

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    wf_client.purge_workflow(instance_id)

    assert state.runtime_status.name == 'COMPLETED'
    assert state.serialized_output == '"ping"'


def test_external_event_unblocks_workflow(wf_client):
    instance_id = wf_client.schedule_new_workflow(
        workflow='external_event_wf', instance_id=_instance_id('event')
    )
    wf_client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

    wf_client.raise_workflow_event(instance_id, event_name='go', data='unlocked')

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    wf_client.purge_workflow(instance_id)

    assert state.runtime_status.name == 'COMPLETED'
    assert state.serialized_output == '"unlocked"'


def test_pause_and_resume_transitions_status(wf_client):
    instance_id = wf_client.schedule_new_workflow(
        workflow='external_event_wf', instance_id=_instance_id('pause')
    )
    wf_client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

    wf_client.pause_workflow(instance_id)
    paused_state = wf_client.get_workflow_state(instance_id)
    assert paused_state is not None
    assert paused_state.runtime_status.name == 'SUSPENDED'

    wf_client.resume_workflow(instance_id)
    wf_client.raise_workflow_event(instance_id, event_name='go', data='resumed')

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    wf_client.purge_workflow(instance_id)

    assert state.runtime_status.name == 'COMPLETED'
    assert state.serialized_output == '"resumed"'


def test_terminate_sets_terminated_status(wf_client):
    instance_id = wf_client.schedule_new_workflow(
        workflow='external_event_wf', instance_id=_instance_id('terminate')
    )
    wf_client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)

    wf_client.terminate_workflow(instance_id)

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    wf_client.purge_workflow(instance_id)

    assert state.runtime_status.name == 'TERMINATED'


def test_purge_removes_completed_instance(wf_client):
    instance_id = wf_client.schedule_new_workflow(
        workflow='echo_input_wf', input='bye', instance_id=_instance_id('purge')
    )
    wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)

    wf_client.purge_workflow(instance_id)

    assert wf_client.get_workflow_state(instance_id) is None


def test_get_state_returns_none_for_unknown_instance(wf_client):
    assert wf_client.get_workflow_state(_instance_id('missing')) is None
