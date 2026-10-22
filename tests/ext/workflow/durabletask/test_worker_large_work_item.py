# -*- coding: utf-8 -*-
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

"""A work item larger than gRPC's 4MB default receive limit still reaches the worker."""

import json
import threading
import time
from collections.abc import Iterator
from concurrent import futures
from unittest.mock import patch

import grpc
from google.protobuf import empty_pb2, wrappers_pb2

import dapr.ext.workflow._durabletask.internal.orchestrator_service_pb2_grpc as stubs
import dapr.ext.workflow._durabletask.internal.protos as pb
import dapr.ext.workflow._durabletask.internal.shared as shared
from dapr.ext.workflow._durabletask import task
from dapr.ext.workflow._durabletask.worker import TaskHubGrpcWorker

# A fan-out of five 1MB activity results is a work item of about 6.3MB.
_PAYLOAD_BYTES = 6 * 1024 * 1024


def payload_length(ctx: task.ActivityContext, data: str) -> int:
    return len(data)


class _Sidecar(stubs.TaskHubSidecarServiceServicer):
    """Serves one large activity work item on every stream until its result arrives."""

    def __init__(self, work_item: pb.WorkItem):
        self._work_item = work_item
        self.streams = 0
        self.response: pb.ActivityResponse | None = None
        self.done = threading.Event()

    def Hello(self, request: empty_pb2.Empty, context: grpc.ServicerContext) -> empty_pb2.Empty:  # noqa: N802
        return empty_pb2.Empty()

    def GetWorkItems(  # noqa: N802
        self, request: pb.GetWorkItemsRequest, context: grpc.ServicerContext
    ) -> Iterator[pb.WorkItem]:
        self.streams += 1
        if not self.done.is_set():
            yield self._work_item
        while context.is_active() and not self.done.is_set():
            time.sleep(0.05)

    def CompleteActivityTask(  # noqa: N802
        self, request: pb.ActivityResponse, context: grpc.ServicerContext
    ) -> pb.CompleteTaskResponse:
        self.response = request
        self.done.set()
        return pb.CompleteTaskResponse()


def test_work_item_larger_than_default_receive_limit_is_processed() -> None:
    activity_input = wrappers_pb2.StringValue(value=json.dumps('x' * _PAYLOAD_BYTES))
    activity_request = pb.ActivityRequest(
        name=task.get_name(payload_length),
        taskId=1,
        workflowInstance=pb.WorkflowInstance(instanceId='instance'),
        input=activity_input,
    )
    sidecar = _Sidecar(pb.WorkItem(activityRequest=activity_request))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    stubs.add_TaskHubSidecarServiceServicer_to_server(sidecar, server)
    port = server.add_insecure_port('127.0.0.1:0')
    server.start()
    worker = TaskHubGrpcWorker(host_address=f'127.0.0.1:{port}')
    worker.add_activity(payload_length)
    worker.start()
    try:
        assert sidecar.done.wait(15), (
            f'no activity result after {sidecar.streams} work item streams: '
            'the worker could not receive the work item'
        )
        assert sidecar.response is not None
        assert sidecar.response.result.value == str(_PAYLOAD_BYTES)
    finally:
        worker.stop()
        server.stop(0)


def test_explicit_receive_limit_is_kept() -> None:
    worker = TaskHubGrpcWorker(channel_options=[('grpc.max_receive_message_length', 1024)])
    with patch.object(grpc, 'insecure_channel') as insecure_channel:
        shared.get_grpc_channel(worker._host_address, options=worker._channel_options)
    options_merged = dict(insecure_channel.call_args.kwargs['options'])
    assert options_merged['grpc.max_receive_message_length'] == 1024
