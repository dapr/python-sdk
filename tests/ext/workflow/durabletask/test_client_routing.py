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

"""Tests for cross-app routing (TaskRouter) support in the durabletask clients."""

from unittest.mock import AsyncMock, MagicMock, patch

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.aio.client import AsyncTaskHubGrpcClient
from dapr.ext.workflow._durabletask.client import TaskHubGrpcClient, new_task_router

TARGET_APP_ID = 'appB'
INSTANCE_ID = 'instance001'


def _make_sync_client() -> TaskHubGrpcClient:
    with patch('grpc.insecure_channel'):
        hub_client = TaskHubGrpcClient(host_address='localhost:1')
    stub = MagicMock()
    stub.StartInstance.return_value = pb.CreateInstanceResponse(instanceId=INSTANCE_ID)
    stub.GetInstance.return_value = pb.GetInstanceResponse(exists=False)
    stub.WaitForInstanceStart.return_value = pb.GetInstanceResponse(exists=False)
    stub.WaitForInstanceCompletion.return_value = pb.GetInstanceResponse(exists=False)
    hub_client._stub = stub
    return hub_client


def _make_async_client() -> AsyncTaskHubGrpcClient:
    hub_client = AsyncTaskHubGrpcClient(host_address='localhost:1')
    stub = AsyncMock()
    stub.StartInstance.return_value = pb.CreateInstanceResponse(instanceId=INSTANCE_ID)
    stub.GetInstance.return_value = pb.GetInstanceResponse(exists=False)
    stub.WaitForInstanceStart.return_value = pb.GetInstanceResponse(exists=False)
    stub.WaitForInstanceCompletion.return_value = pb.GetInstanceResponse(exists=False)
    hub_client._stub = stub
    return hub_client


def _sent_request(stub_method):
    return stub_method.call_args[0][0]


def _assert_routed(req):
    assert req.HasField('router')
    assert req.router.targetAppID == TARGET_APP_ID
    assert req.router.HasField('targetAppID')
    assert req.router.sourceAppID == ''
    assert not req.router.HasField('targetAppNamespace')


def test_new_task_router_none_when_no_app_id():
    assert new_task_router(None) is None


def test_new_task_router_target_app_only():
    router = new_task_router(TARGET_APP_ID)
    assert router.targetAppID == TARGET_APP_ID
    assert not router.HasField('targetAppNamespace')
    assert router.sourceAppID == ''


def test_sync_client_sets_router_when_app_id_given():
    hub_client = _make_sync_client()
    stub = hub_client._stub

    hub_client.schedule_new_orchestration('wf', app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.StartInstance))

    hub_client.get_orchestration_state(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.GetInstance))

    hub_client.wait_for_orchestration_start(INSTANCE_ID, timeout=1, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.WaitForInstanceStart))

    hub_client.wait_for_orchestration_completion(INSTANCE_ID, timeout=1, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.WaitForInstanceCompletion))

    hub_client.raise_orchestration_event(INSTANCE_ID, 'event', app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.RaiseEvent))

    hub_client.terminate_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.TerminateInstance))

    hub_client.suspend_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.SuspendInstance))

    hub_client.resume_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.ResumeInstance))

    hub_client.purge_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.PurgeInstances))


def test_sync_client_no_router_when_app_id_none():
    hub_client = _make_sync_client()
    stub = hub_client._stub

    hub_client.schedule_new_orchestration('wf')
    assert not _sent_request(stub.StartInstance).HasField('router')

    hub_client.get_orchestration_state(INSTANCE_ID)
    assert not _sent_request(stub.GetInstance).HasField('router')

    hub_client.wait_for_orchestration_start(INSTANCE_ID, timeout=1)
    assert not _sent_request(stub.WaitForInstanceStart).HasField('router')

    hub_client.wait_for_orchestration_completion(INSTANCE_ID, timeout=1)
    assert not _sent_request(stub.WaitForInstanceCompletion).HasField('router')

    hub_client.raise_orchestration_event(INSTANCE_ID, 'event')
    assert not _sent_request(stub.RaiseEvent).HasField('router')

    hub_client.terminate_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.TerminateInstance).HasField('router')

    hub_client.suspend_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.SuspendInstance).HasField('router')

    hub_client.resume_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.ResumeInstance).HasField('router')

    hub_client.purge_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.PurgeInstances).HasField('router')


async def test_async_client_sets_router_when_app_id_given():
    hub_client = _make_async_client()
    stub = hub_client._stub

    await hub_client.schedule_new_orchestration('wf', app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.StartInstance))

    await hub_client.get_orchestration_state(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.GetInstance))

    await hub_client.wait_for_orchestration_start(INSTANCE_ID, timeout=1, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.WaitForInstanceStart))

    await hub_client.wait_for_orchestration_completion(INSTANCE_ID, timeout=1, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.WaitForInstanceCompletion))

    await hub_client.raise_orchestration_event(INSTANCE_ID, 'event', app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.RaiseEvent))

    await hub_client.terminate_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.TerminateInstance))

    await hub_client.suspend_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.SuspendInstance))

    await hub_client.resume_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.ResumeInstance))

    await hub_client.purge_orchestration(INSTANCE_ID, app_id=TARGET_APP_ID)
    _assert_routed(_sent_request(stub.PurgeInstances))


async def test_async_client_no_router_when_app_id_none():
    hub_client = _make_async_client()
    stub = hub_client._stub

    await hub_client.schedule_new_orchestration('wf')
    assert not _sent_request(stub.StartInstance).HasField('router')

    await hub_client.get_orchestration_state(INSTANCE_ID)
    assert not _sent_request(stub.GetInstance).HasField('router')

    await hub_client.wait_for_orchestration_start(INSTANCE_ID, timeout=1)
    assert not _sent_request(stub.WaitForInstanceStart).HasField('router')

    await hub_client.wait_for_orchestration_completion(INSTANCE_ID, timeout=1)
    assert not _sent_request(stub.WaitForInstanceCompletion).HasField('router')

    await hub_client.raise_orchestration_event(INSTANCE_ID, 'event')
    assert not _sent_request(stub.RaiseEvent).HasField('router')

    await hub_client.terminate_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.TerminateInstance).HasField('router')

    await hub_client.suspend_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.SuspendInstance).HasField('router')

    await hub_client.resume_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.ResumeInstance).HasField('router')

    await hub_client.purge_orchestration(INSTANCE_ID)
    assert not _sent_request(stub.PurgeInstances).HasField('router')
