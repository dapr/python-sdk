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

import time
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.worker import TaskHubGrpcWorker


class _PingStub:
    """Serves health pings then an unknown work item, and holds the stream open until shutdown."""

    def __init__(self, worker: TaskHubGrpcWorker) -> None:
        self._worker = worker
        self.requests: list[pb.GetWorkItemsRequest] = []

    def Hello(self, *_args: object, **_kwargs: object) -> None:  # noqa: N802
        pass

    def GetWorkItems(self, request: pb.GetWorkItemsRequest) -> Iterator[pb.WorkItem]:  # noqa: N802
        self.requests.append(request)
        for _ in range(3):
            yield pb.WorkItem(healthPing=pb.HealthPing())
        yield pb.WorkItem()
        self._worker._shutdown.wait()


def test_health_ping_advertised_and_ignored_without_reconnecting() -> None:
    worker = TaskHubGrpcWorker()
    worker._logger = MagicMock()
    stub = _PingStub(worker)

    with (
        patch(
            'dapr.ext.workflow._durabletask.worker.shared.get_grpc_channel',
            return_value=MagicMock(),
        ),
        patch(
            'dapr.ext.workflow._durabletask.worker.stubs.TaskHubSidecarServiceStub',
            return_value=stub,
        ),
    ):
        worker.start()
        try:
            # The unknown item follows the pings, so its warning means the pings were handled.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                warnings = [str(c) for c in worker._logger.warning.call_args_list]
                if any('Unexpected work item type: None' in w for w in warnings):
                    break
                time.sleep(0.01)
            else:
                raise AssertionError(f'unknown work item never reached the dispatcher: {warnings}')
        finally:
            worker.stop()

    assert len(stub.requests) == 1, 'worker reconnected, so a work item tore down the stream'
    assert pb.WORKER_CAPABILITY_HEALTH_PING in stub.requests[0].capabilities
    assert not any('Unexpected work item type: healthPing' in w for w in warnings)
