# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

End-to-end tests for cross-app workflow client operations.

Two sidecars are started: a host app that registers the workflow, and a caller
app that registers nothing. Every operation is issued from the caller's
DaprWorkflowClient with app_id pointing at the host, proving the target app ID
travels on the wire and the runtime routes to the owning app.

Requires a daprd that supports cross-app workflow operations; against an older
runtime the app_id is ignored and the caller would act on its own app.
"""

import time

import pytest

from dapr.ext.workflow import DaprWorkflowClient
from tests.integration.apps.workflow_host import EVENT_NAME, WORKFLOW_NAME

pytestmark = pytest.mark.dapr_head

HOST_APP_ID = 'wf-cross-app-host'
HOST_GRPC_PORT = 13541
HOST_HTTP_PORT = 3541
HOST_INTERNAL_GRPC_PORT = 13542
HOST_METRICS_PORT = 9141

CALLER_APP_ID = 'wf-cross-app-caller'
CALLER_GRPC_PORT = 13551
CALLER_HTTP_PORT = 3551
CALLER_INTERNAL_GRPC_PORT = 13552
CALLER_METRICS_PORT = 9151

WORKFLOW_READY_TIMEOUT = 30
STATUS_TIMEOUT = 30


@pytest.fixture(scope='module', autouse=True)
def sidecars(dapr_env, apps_dir):
    """Starts the workflow host app and a caller app with its own sidecar."""
    dapr_env.start_sidecar(
        app_id=HOST_APP_ID,
        grpc_port=HOST_GRPC_PORT,
        http_port=HOST_HTTP_PORT,
        internal_grpc_port=HOST_INTERNAL_GRPC_PORT,
        metrics_port=HOST_METRICS_PORT,
        app_cmd=f'python3 {apps_dir / "workflow_host.py"}',
    )
    dapr_env.start_sidecar(
        app_id=CALLER_APP_ID,
        grpc_port=CALLER_GRPC_PORT,
        http_port=CALLER_HTTP_PORT,
        internal_grpc_port=CALLER_INTERNAL_GRPC_PORT,
        metrics_port=CALLER_METRICS_PORT,
    )


@pytest.fixture(scope='module')
def caller_client():
    """A workflow client bound to the caller sidecar, which hosts no workflows."""
    client = DaprWorkflowClient(port=str(CALLER_GRPC_PORT))
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope='module')
def host_client():
    """A workflow client bound to the host sidecar, used only to corroborate state."""
    client = DaprWorkflowClient(port=str(HOST_GRPC_PORT))
    try:
        yield client
    finally:
        client.close()


def _schedule_on_host(caller_client: DaprWorkflowClient) -> str:
    """Schedules the host's workflow from the caller and waits for it to run.

    The host worker registers its workflow asynchronously after its sidecar
    reports ready, so scheduling is retried until the host has it.
    """
    deadline = time.monotonic() + WORKFLOW_READY_TIMEOUT
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            instance_id = caller_client.schedule_new_workflow(
                workflow=WORKFLOW_NAME, app_id=HOST_APP_ID
            )
            state = caller_client.wait_for_workflow_start(
                instance_id, app_id=HOST_APP_ID, timeout_in_seconds=10
            )
            if state is not None:
                return instance_id
        except Exception as exc:  # noqa: BLE001 - retried until the host is up
            last_error = exc
        time.sleep(0.5)
    raise AssertionError(f'host app never accepted a cross-app schedule: {last_error}')


def _wait_until_absent(client: DaprWorkflowClient, instance_id: str) -> None:
    deadline = time.monotonic() + STATUS_TIMEOUT
    while time.monotonic() < deadline:
        if client.get_workflow_state(instance_id) is None:
            return
        time.sleep(0.2)
    raise AssertionError(f'{instance_id} was still present after purge')


def _wait_for_status(client: DaprWorkflowClient, instance_id: str, expected: str) -> None:
    deadline = time.monotonic() + STATUS_TIMEOUT
    seen = None
    while time.monotonic() < deadline:
        state = client.get_workflow_state(instance_id, app_id=HOST_APP_ID)
        seen = None if state is None else state.runtime_status.name
        if seen == expected:
            return
        time.sleep(0.2)
    raise AssertionError(f'expected status {expected}, last saw {seen}')


def test_cross_app_schedule_targets_the_host_app(caller_client, host_client):
    """A workflow scheduled with app_id runs on the host, not on the caller."""
    instance_id = _schedule_on_host(caller_client)

    hosted = host_client.get_workflow_state(instance_id)
    assert hosted is not None
    assert hosted.name == WORKFLOW_NAME

    local_to_caller = caller_client.get_workflow_state(instance_id)
    assert local_to_caller is None


def test_cross_app_pause_and_resume(caller_client):
    """Pause and resume drive the remote instance through SUSPENDED and back."""
    instance_id = _schedule_on_host(caller_client)

    caller_client.pause_workflow(instance_id, app_id=HOST_APP_ID)
    _wait_for_status(caller_client, instance_id, 'SUSPENDED')

    caller_client.resume_workflow(instance_id, app_id=HOST_APP_ID)
    _wait_for_status(caller_client, instance_id, 'RUNNING')


def test_cross_app_raise_event_completes_and_purge_removes(caller_client, host_client):
    """Raising the awaited event completes the remote workflow, then purge deletes it."""
    instance_id = _schedule_on_host(caller_client)

    caller_client.raise_workflow_event(instance_id, EVENT_NAME, data='finished', app_id=HOST_APP_ID)
    state = caller_client.wait_for_workflow_completion(
        instance_id, app_id=HOST_APP_ID, timeout_in_seconds=STATUS_TIMEOUT
    )
    assert state is not None
    assert state.runtime_status.name == 'COMPLETED'

    caller_client.purge_workflow(instance_id, app_id=HOST_APP_ID)
    _wait_until_absent(host_client, instance_id)


def test_cross_app_terminate(caller_client):
    """Terminate stops the remote instance."""
    instance_id = _schedule_on_host(caller_client)

    caller_client.terminate_workflow(instance_id, app_id=HOST_APP_ID)
    _wait_for_status(caller_client, instance_id, 'TERMINATED')
