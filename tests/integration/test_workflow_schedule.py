# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""End-to-end tests for the workflow schedule APIs of DaprWorkflowClient.

Requires a daprd with workflow schedule support (dapr master, 1.20 onwards); an
older sidecar answers UNIMPLEMENTED.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Any, Callable, Iterator

import grpc
import pytest

from dapr.ext.workflow import (
    DaprWorkflowClient,
    DaprWorkflowContext,
    WorkflowRuntime,
    WorkflowScheduleRun,
    WorkflowScheduleState,
    WorkflowScheduleStatus,
    WorkflowStatus,
)
from tests.wait_utils import wait_until

pytestmark = pytest.mark.dapr_head

HOST = '127.0.0.1'
GRPC_PORT = '13501'
TIMEOUT_S = 30


def report_workflow(ctx: DaprWorkflowContext, region: str) -> str:
    return f'report for {region}'


@pytest.fixture(scope='module')
def client(dapr_env) -> Iterator[DaprWorkflowClient]:
    dapr_env.start_sidecar(app_id='test-workflow-schedule')
    runtime = WorkflowRuntime(host=HOST, port=GRPC_PORT)
    runtime.register_workflow(report_workflow)
    runtime.start()
    workflow_client = DaprWorkflowClient(host=HOST, port=GRPC_PORT)
    try:
        yield workflow_client
    finally:
        workflow_client.close()
        runtime.shutdown()


@contextmanager
def _created(client: DaprWorkflowClient, name: str, schedule: str, **kwargs: Any) -> Iterator[None]:
    """Creates a schedule for the block and deletes it afterwards.

    overwrite=True replaces a schedule an aborted earlier run left behind.
    """
    client.create_workflow_schedule(name, report_workflow, schedule, overwrite=True, **kwargs)
    try:
        yield
    finally:
        try:
            client.delete_workflow_schedule(name)
        except grpc.RpcError as error:
            if error.code() != grpc.StatusCode.NOT_FOUND:
                raise


def _status_of(client: DaprWorkflowClient, name: str) -> WorkflowScheduleStatus:
    status = client.get_workflow_schedule(name).status
    assert status is not None
    return status


def _assert_rpc_code(call: Callable[[], object], code: grpc.StatusCode) -> None:
    with pytest.raises(grpc.RpcError) as error:
        call()
    assert error.value.code() == code


def test_schedule_runs_and_completes(client):
    name = 'sched-runs'
    with _created(client, name, '@every 1s', input='eu', repeats=2):

        def completed_status() -> WorkflowScheduleStatus | None:
            status = _status_of(client, name)
            return status if status.state == WorkflowScheduleState.COMPLETED else None

        status = wait_until(completed_status, timeout=TIMEOUT_S, interval=0.5)
        assert status.run_count == 2
        assert status.next_run_time is None
        assert status.last_run_time is not None
        assert status.last_run is not None
        assert status.last_run.instance_id.startswith(f'{name}_')

        def completed_last_run() -> WorkflowScheduleRun | None:
            last_run = _status_of(client, name).last_run
            if last_run is None or last_run.runtime_status != WorkflowStatus.COMPLETED:
                return None
            return last_run

        last_run = wait_until(completed_last_run, timeout=TIMEOUT_S, interval=0.5)
        assert last_run.serialized_output == '"report for eu"'

        schedule = client.get_workflow_schedule(name)
        assert schedule.workflow_name == 'report_workflow'
        assert schedule.schedule == '@every 1s'
        assert schedule.serialized_input == '"eu"'
        assert schedule.repeats == 2
        assert schedule.skip_missed is False

        _assert_rpc_code(
            lambda: client.trigger_workflow_schedule(name), grpc.StatusCode.FAILED_PRECONDITION
        )

        run_ids = list(client.iter_workflow_instance_ids(instance_id_prefix=f'{name}_'))
        assert len(run_ids) == 2
        for run_id in run_ids:
            client.wait_for_workflow_completion(run_id, timeout_in_seconds=TIMEOUT_S)
            client.purge_workflow(run_id)


def test_trigger_starts_a_run_now(client):
    name = 'sched-manual'
    with _created(client, name, '@every 1h', input='us'):
        run_id = client.trigger_workflow_schedule(name)
        assert run_id.startswith(f'{name}_')
        assert run_id.endswith('_manual')

        run_state = client.wait_for_workflow_completion(run_id, timeout_in_seconds=TIMEOUT_S)
        assert run_state is not None
        assert run_state.runtime_status == WorkflowStatus.COMPLETED
        assert run_state.serialized_output == '"report for us"'
        client.purge_workflow(run_id)

        status = _status_of(client, name)
        assert status.run_count == 1
        assert status.state == WorkflowScheduleState.ACTIVE
        assert status.next_run_time is not None

        client.create_workflow_schedule(
            name, report_workflow, '@every 1h', input='us', overwrite=True
        )
        assert _status_of(client, name).run_count == 0

        client.delete_workflow_schedule(name)
        _assert_rpc_code(lambda: client.get_workflow_schedule(name), grpc.StatusCode.NOT_FOUND)
        _assert_rpc_code(lambda: client.delete_workflow_schedule(name), grpc.StatusCode.NOT_FOUND)


def test_list_pages_through_schedules(client):
    names = [f'sched-list-{i}' for i in range(3)]
    with ExitStack() as stack:
        for name in names:
            stack.enter_context(_created(client, name, '@every 1h'))

        pages = [client.list_workflow_schedules(page_size=2)]
        while pages[-1].continuation_token is not None:
            next_page = client.list_workflow_schedules(
                page_size=2, continuation_token=pages[-1].continuation_token
            )
            pages.append(next_page)

        listed = [schedule for page in pages for schedule in page.schedules]
        assert len(pages) >= 2
        assert set(names) <= {schedule.name for schedule in listed}
        assert all(schedule.status is not None for schedule in listed)


def test_create_errors(client):
    name = 'sched-dup'
    with _created(client, name, '@every 1h'):
        _assert_rpc_code(
            lambda: client.create_workflow_schedule(name, report_workflow, '@every 1h'),
            grpc.StatusCode.ALREADY_EXISTS,
        )

    _assert_rpc_code(
        lambda: client.create_workflow_schedule('sched-bad-cron', report_workflow, 'not a cron'),
        grpc.StatusCode.INVALID_ARGUMENT,
    )
    _assert_rpc_code(
        lambda: client.create_workflow_schedule(
            'dapr-internal-schedule-x', report_workflow, '@every 1h'
        ),
        grpc.StatusCode.INVALID_ARGUMENT,
    )
    _assert_rpc_code(lambda: client.get_workflow_schedule('missing'), grpc.StatusCode.NOT_FOUND)
    _assert_rpc_code(lambda: client.delete_workflow_schedule('missing'), grpc.StatusCode.NOT_FOUND)
