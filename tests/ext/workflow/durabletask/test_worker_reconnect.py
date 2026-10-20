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

import asyncio
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Optional, Union
from unittest.mock import MagicMock, patch

import grpc
import pytest

import dapr.ext.workflow._durabletask.internal.helpers as ph
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.worker import (
    _CONNECT_HELLO_TIMEOUT,
    _RESULT_SEND_TIMEOUT,
    TaskHubGrpcWorker,
)


class _RpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode) -> None:
        self._code = code

    def code(self) -> grpc.StatusCode:
        return self._code

    def details(self) -> str:
        return self._code.name


class _SidecarStub:
    """One connection's stub: serves one work-item stream that stays open until ``end_stream``."""

    def __init__(
        self,
        worker: TaskHubGrpcWorker,
        hello_error: Optional[Exception] = None,
        hello_gate: Optional[threading.Event] = None,
        work_items: Sequence[pb.WorkItem] = (),
    ):
        self._worker = worker
        self._hello_error = hello_error
        self._hello_gate = hello_gate
        self._work_items = list(work_items)
        self.hello_timeouts: list[Optional[float]] = []
        self.results: list[Union[pb.ActivityResponse, pb.WorkflowResponse]] = []
        self.result_timeouts: list[Optional[float]] = []
        self.result_received = threading.Event()
        self.stream_open = threading.Event()
        self._stream_end = threading.Event()

    def Hello(self, *_args: object, timeout: Optional[float] = None) -> None:  # noqa: N802
        self.hello_timeouts.append(timeout)
        if self._hello_gate is not None:
            assert self._hello_gate.wait(5)
        if self._hello_error is not None:
            raise self._hello_error

    def GetWorkItems(self, _request: pb.GetWorkItemsRequest) -> Iterator[pb.WorkItem]:  # noqa: N802
        self.stream_open.set()
        yield from self._work_items
        while not self._stream_end.wait(0.01):
            if self._worker._shutdown.is_set():
                return
        yield from ()

    def CompleteActivityTask(  # noqa: N802
        self, response: pb.ActivityResponse, timeout: Optional[float] = None
    ) -> None:
        self._record_result(response, timeout)

    def CompleteOrchestratorTask(  # noqa: N802
        self, response: pb.WorkflowResponse, timeout: Optional[float] = None
    ) -> None:
        self._record_result(response, timeout)

    def _record_result(
        self, response: Union[pb.ActivityResponse, pb.WorkflowResponse], timeout: Optional[float]
    ) -> None:
        self.results.append(response)
        self.result_timeouts.append(timeout)
        self.result_received.set()

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
    return TaskHubGrpcWorker(keepalive_interval=0, stop_timeout=5)


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


def _wait_until(condition: Callable[[], bool], timeout: float = 5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_worker_is_not_ready_while_its_stream_is_down() -> None:
    worker = _worker()
    first = _SidecarStub(worker)
    reconnect_gate = threading.Event()
    second = _SidecarStub(worker, hello_gate=reconnect_gate)
    sidecar = _FakeSidecar(worker, [first, second])

    with _running(worker, sidecar):
        assert worker.is_worker_ready()

        first.end_stream()
        assert _wait_until(lambda: not worker.is_worker_ready()), 'still ready without a stream'

        reconnect_gate.set()
        assert second.stream_open.wait(5)
        assert _wait_until(worker.is_worker_ready), 'not ready again after reconnecting'

    assert not worker.is_worker_ready()


class _SlowWork:
    """A registered activity or workflow that runs until the test releases it."""

    def __init__(self, worker: TaskHubGrpcWorker, kind: str) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

        def run(_ctx: object, _input: object) -> str:
            self.started.set()
            assert self.release.wait(5)
            return 'done'

        async def run_async(_ctx: object, _input: object) -> str:
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0.01)
            return 'done'

        if kind == 'workflow':
            name = worker.add_orchestrator(run)
            started = ph.new_execution_started_event(name, 'instance')
            request = pb.WorkflowRequest(instanceId='instance', newEvents=[started])
            self.work_item = pb.WorkItem(workflowRequest=request)
            return
        name = worker.add_activity(run_async if kind == 'async activity' else run)
        instance = pb.WorkflowInstance(instanceId='instance')
        activity_request = pb.ActivityRequest(name=name, taskId=1, workflowInstance=instance)
        self.work_item = pb.WorkItem(activityRequest=activity_request)


@pytest.mark.parametrize('kind', ['activity', 'async activity', 'workflow'])
def test_result_that_outlives_its_stream_is_sent_on_the_new_connection(kind: str) -> None:
    """The work item's own channel is closed after a reconnect, so its result would be lost."""
    worker = _worker()
    work = _SlowWork(worker, kind)
    first = _SidecarStub(worker, work_items=[work.work_item])
    second = _SidecarStub(worker)
    sidecar = _FakeSidecar(worker, [first, second])

    with _running(worker, sidecar):
        assert work.started.wait(5)
        first.end_stream()
        assert second.stream_open.wait(5)

        work.release.set()
        assert second.result_received.wait(5), 'result never reached the new connection'

    assert first.results == []
    assert len(second.results) == 1
    assert second.result_timeouts == [_RESULT_SEND_TIMEOUT]


def test_result_ready_during_a_reconnect_waits_for_the_new_connection() -> None:
    worker = _worker()
    work = _SlowWork(worker, 'activity')
    first = _SidecarStub(worker, work_items=[work.work_item])
    reconnect_gate = threading.Event()
    second = _SidecarStub(worker, hello_gate=reconnect_gate)
    sidecar = _FakeSidecar(worker, [first, second])

    with _running(worker, sidecar):
        assert work.started.wait(5)
        first.end_stream()
        assert _wait_until(lambda: not worker.is_worker_ready())
        work.release.set()
        time.sleep(0.2)  # the result is ready while there is no connection to send it on
        assert second.results == [], 'result sent before the new connection passed its Hello'

        reconnect_gate.set()
        assert second.result_received.wait(5), 'result was dropped instead of waiting'

    assert first.results == []


def test_result_ready_during_a_failed_reconnect_waits_for_a_healthy_one() -> None:
    worker = _worker()
    work = _SlowWork(worker, 'activity')
    first = _SidecarStub(worker, work_items=[work.work_item])
    reconnect_gate = threading.Event()
    unavailable = _RpcError(grpc.StatusCode.UNAVAILABLE)
    failing = _SidecarStub(worker, hello_error=unavailable, hello_gate=reconnect_gate)
    healthy = _SidecarStub(worker)
    sidecar = _FakeSidecar(worker, [first, failing, healthy])

    with _running(worker, sidecar):
        assert work.started.wait(5)
        first.end_stream()
        assert _wait_until(lambda: len(failing.hello_timeouts) == 1)
        work.release.set()
        time.sleep(0.2)  # the result is ready while the failing connection is in its Hello

        reconnect_gate.set()
        assert healthy.result_received.wait(10), 'result was lost on the failed connection'

    assert first.results == []
    assert failing.results == []


def test_result_is_dropped_when_the_worker_stops_before_reconnecting() -> None:
    worker = _worker()
    stub = MagicMock()
    worker._set_connection(MagicMock(), stub)
    worker._retire_connection()
    worker._shutdown.set()

    started = time.monotonic()
    worker._deliver_activity_response(pb.ActivityRequest(), pb.ActivityResponse(), '', 'instance')

    assert time.monotonic() - started < 1, 'a stopping worker waited for a reconnect'
    stub.CompleteActivityTask.assert_not_called()


def test_retired_connection_is_never_handed_out() -> None:
    worker = _worker()
    worker._set_connection(MagicMock(), MagicMock())
    worker._retire_connection()

    with worker._sidecar_stub(wait=0) as stub:
        assert stub is None


def test_channel_is_closed_only_after_the_calls_in_flight_on_it() -> None:
    """Starting a call on a closed channel with interceptors crashes the process in grpcio."""
    worker = _worker()
    channel = MagicMock()
    worker._set_connection(channel, MagicMock())

    with worker._sidecar_stub(wait=0) as stub:
        assert stub is not None
        worker._retire_connection()
        closer = threading.Thread(target=worker._close_channel, args=(channel,))
        closer.start()
        closer.join(0.2)
        assert closer.is_alive()
        channel.close.assert_not_called()

    closer.join(5)
    channel.close.assert_called_once()


def _stoppable_worker() -> TaskHubGrpcWorker:
    worker = _worker()
    worker._runLoop = MagicMock()
    worker._runLoop.is_alive.return_value = False
    return worker


def _hold_call(worker: TaskHubGrpcWorker, release: threading.Event) -> threading.Thread:
    """Starts a thread that holds a call in flight on the current connection until released."""
    call_started = threading.Event()

    def held_call() -> None:
        with worker._sidecar_stub(wait=0):
            call_started.set()
            release.wait(5)

    caller = threading.Thread(target=held_call)
    caller.start()
    assert call_started.wait(5)
    return caller


def test_result_ready_while_the_worker_stops_is_still_delivered() -> None:
    worker = _stoppable_worker()
    stub = MagicMock()
    worker._set_connection(MagicMock(), stub)
    release = threading.Event()
    caller = _hold_call(worker, release)

    stopper = threading.Thread(target=worker.stop)
    stopper.start()
    assert _wait_until(worker._shutdown.is_set)
    worker._deliver_activity_response(pb.ActivityRequest(), pb.ActivityResponse(), '', 'instance')
    release.set()
    caller.join(5)
    stopper.join(10)

    stub.CompleteActivityTask.assert_called_once()


def test_stop_never_closes_a_channel_with_a_call_in_flight() -> None:
    """Closing early could land between a holder's two calls, and the second would crash."""
    worker = _stoppable_worker()
    channel = MagicMock()
    worker._set_connection(channel, MagicMock())
    release = threading.Event()
    caller = _hold_call(worker, release)

    with patch('dapr.ext.workflow._durabletask.worker._STOP_DRAIN_TIMEOUT', 0.1):
        stopper = threading.Thread(target=worker.stop)
        stopper.start()
        stopper.join(0.5)
    assert stopper.is_alive()
    channel.close.assert_not_called()

    release.set()
    caller.join(5)
    stopper.join(10)
    channel.close.assert_called_once()


def test_connection_is_not_published_once_the_worker_is_stopping() -> None:
    worker = _worker()
    worker._shutdown.set()

    assert not worker._set_connection(MagicMock(), MagicMock())
    with worker._sidecar_stub(wait=0) as stub:
        assert stub is None
