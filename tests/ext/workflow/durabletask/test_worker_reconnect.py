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

"""How the worker behaves when its connection to the sidecar drops and comes back."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional
from unittest.mock import MagicMock, patch

import grpc

import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.worker import _CONNECT_HELLO_TIMEOUT, TaskHubGrpcWorker


class _RpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode) -> None:
        self._code = code

    def code(self) -> grpc.StatusCode:
        return self._code

    def details(self) -> str:
        return self._code.name


class _SidecarStub:
    """One connection's stub: serves one work-item stream that stays open until ``end_stream``."""

    def __init__(self, worker: TaskHubGrpcWorker, hello_error: Optional[Exception] = None):
        self._worker = worker
        self._hello_error = hello_error
        self.hello_timeouts: list[Optional[float]] = []
        self.stream_open = threading.Event()
        self._stream_end = threading.Event()

    def Hello(self, *_args: object, timeout: Optional[float] = None) -> None:  # noqa: N802
        self.hello_timeouts.append(timeout)
        if self._hello_error is not None:
            raise self._hello_error

    def GetWorkItems(self, _request: pb.GetWorkItemsRequest) -> Iterator[pb.WorkItem]:  # noqa: N802
        self.stream_open.set()
        while not self._stream_end.wait(0.01):
            if self._worker._shutdown.is_set():
                return
        yield from ()

    def end_stream(self) -> None:
        self._stream_end.set()


class _FakeSidecar:
    """Hands the worker a new channel and stub for each connection it opens."""

    def __init__(self, worker: TaskHubGrpcWorker, stubs: list[_SidecarStub]) -> None:
        self._pending_stubs = list(stubs)
        self.channels: list[MagicMock] = []
        self._stub_by_channel: dict[int, _SidecarStub] = {}

    def channel(self, *_args: object, **_kwargs: object) -> MagicMock:
        new_channel = MagicMock(name=f'channel-{len(self.channels)}')
        self._stub_by_channel[id(new_channel)] = self._pending_stubs.pop(0)
        self.channels.append(new_channel)
        return new_channel

    def stub(self, channel: MagicMock) -> _SidecarStub:
        return self._stub_by_channel[id(channel)]


@contextmanager
def _running(worker: TaskHubGrpcWorker, sidecar: _FakeSidecar) -> Iterator[None]:
    with (
        patch(
            'dapr.ext.workflow._durabletask.worker.shared.get_grpc_channel',
            side_effect=sidecar.channel,
        ),
        patch(
            'dapr.ext.workflow._durabletask.worker.stubs.TaskHubSidecarServiceStub',
            side_effect=sidecar.stub,
        ),
    ):
        worker.start()
        try:
            yield
        finally:
            worker.stop()


def _worker() -> TaskHubGrpcWorker:
    worker = TaskHubGrpcWorker(keepalive_interval=0, stop_timeout=5)
    worker._logger = MagicMock()
    return worker


def test_connect_hello_has_a_deadline() -> None:
    """A Hello that can block forever would stop the worker from ever reconnecting."""
    worker = _worker()
    stub = _SidecarStub(worker)
    sidecar = _FakeSidecar(worker, [stub])

    with _running(worker, sidecar):
        assert stub.stream_open.wait(5)

    assert stub.hello_timeouts == [_CONNECT_HELLO_TIMEOUT]


def test_failed_connect_closes_its_channel() -> None:
    worker = _worker()
    timed_out = _SidecarStub(worker, hello_error=_RpcError(grpc.StatusCode.DEADLINE_EXCEEDED))
    healthy = _SidecarStub(worker)
    sidecar = _FakeSidecar(worker, [timed_out, healthy])

    with _running(worker, sidecar):
        assert healthy.stream_open.wait(10)

    sidecar.channels[0].close.assert_called_once()
