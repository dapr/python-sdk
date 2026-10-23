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
    _CONNECT_HELLO_STEP_TIMEOUT,
    _MAX_RECONNECT_BACKOFF_MS,
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


def _unreachable_hello(
    *_args: object, timeout: Optional[float] = None, wait_for_ready: bool = False
) -> None:
    """Behaves as a Hello on a channel that cannot connect to the sidecar."""
    if not wait_for_ready:
        raise _RpcError(grpc.StatusCode.UNAVAILABLE)
    time.sleep(timeout or 0)
    raise _RpcError(grpc.StatusCode.DEADLINE_EXCEEDED)


class _SidecarStub:
    """The worker's one stub: serves a work-item stream per connect, each open until ended.

    ``hello_errors`` and ``hello_gates`` apply to successive Hellos, so a test can fail or hold
    a reconnect while earlier connects succeed. Likewise, ``open_errors`` fail successive attempts
    to open a stream, and ``stream_errors`` break successive streams once their work items are
    read. With ``sidecar_down``, every Hello behaves as on a channel that cannot connect.
    """

    def __init__(
        self,
        worker: TaskHubGrpcWorker,
        hello_errors: Sequence[Optional[Exception]] = (),
        hello_gates: Sequence[Optional[threading.Event]] = (),
        work_items: Sequence[pb.WorkItem] = (),
        open_errors: Sequence[Optional[Exception]] = (),
        stream_errors: Sequence[Optional[Exception]] = (),
        sidecar_down: bool = False,
    ):
        self._worker = worker
        self._sidecar_down = sidecar_down
        self._hello_errors = list(hello_errors)
        self._hello_gates = list(hello_gates)
        self._work_items = list(work_items)
        self._open_errors = list(open_errors)
        self._stream_errors = list(stream_errors)
        self.hello_timeouts: list[Optional[float]] = []
        self.hello_waits_for_ready: list[bool] = []
        self.results: list[Union[pb.ActivityResponse, pb.WorkflowResponse]] = []
        self.result_kwargs: list[dict[str, object]] = []
        self.result_received = threading.Event()
        self.streams_opened = 0
        self._stream_end = threading.Event()

    def Hello(  # noqa: N802
        self, *_args: object, timeout: Optional[float] = None, wait_for_ready: bool = False
    ) -> None:
        self.hello_timeouts.append(timeout)
        self.hello_waits_for_ready.append(wait_for_ready)
        if self._sidecar_down:
            _unreachable_hello(timeout=timeout, wait_for_ready=wait_for_ready)
        gate = self._hello_gates.pop(0) if self._hello_gates else None
        if gate is not None:
            assert gate.wait(5)
        error = self._hello_errors.pop(0) if self._hello_errors else None
        if error is not None:
            raise error

    def GetWorkItems(self, _request: pb.GetWorkItemsRequest) -> Iterator[pb.WorkItem]:  # noqa: N802
        open_error = self._open_errors.pop(0) if self._open_errors else None
        if open_error is not None:
            raise open_error
        return self._stream()

    def _stream(self) -> Iterator[pb.WorkItem]:
        self.streams_opened += 1
        self._stream_end.clear()
        work_items, self._work_items = self._work_items, []
        yield from work_items
        stream_error = self._stream_errors.pop(0) if self._stream_errors else None
        if stream_error is not None:
            raise stream_error
        while not self._stream_end.wait(0.01):
            if self._worker._shutdown.is_set():
                return

    def CompleteActivityTask(  # noqa: N802
        self, response: pb.ActivityResponse, **kwargs: object
    ) -> None:
        self._record_result(response, kwargs)

    def CompleteOrchestratorTask(  # noqa: N802
        self, response: pb.WorkflowResponse, **kwargs: object
    ) -> None:
        self._record_result(response, kwargs)

    def _record_result(
        self, response: Union[pb.ActivityResponse, pb.WorkflowResponse], kwargs: dict[str, object]
    ) -> None:
        self.results.append(response)
        self.result_kwargs.append(kwargs)
        self.result_received.set()

    def end_stream(self) -> None:
        self._stream_end.set()


@contextmanager
def _running(worker: TaskHubGrpcWorker, stub: _SidecarStub) -> Iterator[MagicMock]:
    """Runs ``worker`` against ``stub``, yielding the patched channel factory."""
    with (
        patch('dapr.ext.workflow._durabletask.worker.shared.get_grpc_channel') as get_channel,
        patch(
            'dapr.ext.workflow._durabletask.worker.stubs.TaskHubSidecarServiceStub',
            return_value=stub,
        ),
    ):
        worker.start()
        try:
            yield get_channel
        finally:
            worker.stop()


def _worker() -> TaskHubGrpcWorker:
    return TaskHubGrpcWorker(keepalive_interval=0, stop_timeout=5)


def _wait_until(condition: Callable[[], bool], timeout: float = 5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_connect_hello_has_a_deadline() -> None:
    """A Hello that can block forever would stop the worker from ever reconnecting."""
    worker = _worker()
    stub = _SidecarStub(worker)

    with _running(worker, stub):
        assert _wait_until(lambda: stub.streams_opened == 1)

    assert stub.hello_timeouts == [_CONNECT_HELLO_STEP_TIMEOUT]
    assert stub.hello_waits_for_ready == [True]


def test_stop_does_not_wait_out_the_connect_hello_during_an_outage() -> None:
    """stop() waits for calls in flight, so a Hello held for its whole deadline would hold it."""
    worker = _worker()
    stub = _SidecarStub(worker, sidecar_down=True)

    def start() -> None:
        with pytest.raises(RuntimeError, match='stopped before'):
            worker.start()

    with (
        patch('dapr.ext.workflow._durabletask.worker.shared.get_grpc_channel'),
        patch(
            'dapr.ext.workflow._durabletask.worker.stubs.TaskHubSidecarServiceStub',
            return_value=stub,
        ),
    ):
        starter = threading.Thread(target=start)
        starter.start()
        assert _wait_until(lambda: len(stub.hello_timeouts) > 0)

        stop_started = time.monotonic()
        worker.stop()
        stop_duration = time.monotonic() - stop_started
        starter.join(5)

    assert stop_duration < 5, f'stop() took {stop_duration:.1f}s while the sidecar was down'


def test_reconnects_reuse_the_one_channel() -> None:
    """gRPC reconnects a channel on its own, so only the work-item stream is re-opened."""
    worker = _worker()
    timed_out = _RpcError(grpc.StatusCode.DEADLINE_EXCEEDED)
    stub = _SidecarStub(worker, hello_errors=[None, timed_out])

    with _running(worker, stub) as get_channel:
        assert _wait_until(lambda: stub.streams_opened == 1)
        stub.end_stream()
        assert _wait_until(lambda: stub.streams_opened == 2, timeout=10)
        channel = get_channel.return_value
        channel.close.assert_not_called()

    get_channel.assert_called_once()
    channel.close.assert_called_once()


def test_stream_that_breaks_is_reopened_on_the_one_channel() -> None:
    worker = _worker()
    stub = _SidecarStub(worker, stream_errors=[ValueError('stream broke')])
    history_cache = worker._history_cache

    with (
        patch.object(history_cache, 'reset', wraps=history_cache.reset) as reset_cache,
        _running(worker, stub) as get_channel,
    ):
        assert _wait_until(lambda: stub.streams_opened == 2), 'broken stream was not reopened'
        assert _wait_until(worker.is_worker_ready), 'not ready again after reopening'
        reset_cache.assert_called()
        get_channel.return_value.close.assert_not_called()

    get_channel.assert_called_once()


def test_stream_that_fails_to_open_is_retried_on_the_one_channel() -> None:
    worker = _worker()
    stub = _SidecarStub(worker, open_errors=[_RpcError(grpc.StatusCode.UNAVAILABLE)])
    history_cache = worker._history_cache

    with (
        patch.object(history_cache, 'reset', wraps=history_cache.reset) as reset_cache,
        _running(worker, stub) as get_channel,
    ):
        assert _wait_until(lambda: stub.streams_opened == 1), 'stream open was not retried'
        assert worker.is_worker_ready()
        reset_cache.assert_called()
        get_channel.return_value.close.assert_not_called()

    get_channel.assert_called_once()


def test_channel_caps_grpc_reconnect_backoff_and_keeps_caller_options() -> None:
    worker = TaskHubGrpcWorker(channel_options=[('grpc.max_reconnect_backoff_ms', 1_000)])

    with patch('dapr.ext.workflow._durabletask.worker.shared.get_grpc_channel') as get_channel:
        worker._open_channel()

    options = get_channel.call_args.kwargs['options']
    assert options[0] == ('grpc.max_reconnect_backoff_ms', _MAX_RECONNECT_BACKOFF_MS)
    assert options[-1] == ('grpc.max_reconnect_backoff_ms', 1_000), 'caller option must win'


def test_worker_is_not_ready_while_its_stream_is_down() -> None:
    worker = _worker()
    reconnect_gate = threading.Event()
    stub = _SidecarStub(worker, hello_gates=[None, reconnect_gate])

    with _running(worker, stub):
        assert worker.is_worker_ready()

        stub.end_stream()
        assert _wait_until(lambda: not worker.is_worker_ready()), 'still ready without a stream'

        reconnect_gate.set()
        assert _wait_until(lambda: stub.streams_opened == 2)
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
def test_result_that_outlives_its_stream_is_still_delivered(kind: str) -> None:
    worker = _worker()
    work = _SlowWork(worker, kind)
    stub = _SidecarStub(worker, work_items=[work.work_item])

    with _running(worker, stub):
        assert work.started.wait(5)
        stub.end_stream()
        assert _wait_until(lambda: stub.streams_opened == 2)

        work.release.set()
        assert stub.result_received.wait(5), 'result was not delivered'

    assert len(stub.results) == 1


@pytest.mark.parametrize('kind', ['activity', 'workflow'])
def test_result_waits_for_the_channel_within_a_deadline(kind: str) -> None:
    """A result ready during a reconnect waits for the channel instead of failing fast."""
    worker = _worker()
    work = _SlowWork(worker, kind)
    stub = _SidecarStub(worker, work_items=[work.work_item])

    with _running(worker, stub):
        assert work.started.wait(5)
        work.release.set()
        assert stub.result_received.wait(5)

    assert stub.result_kwargs == [{'timeout': _RESULT_SEND_TIMEOUT, 'wait_for_ready': True}]


def _worker_with_channel() -> tuple[TaskHubGrpcWorker, MagicMock, MagicMock]:
    worker = _worker()
    worker._runLoop = MagicMock()
    worker._runLoop.is_alive.return_value = False
    channel = MagicMock()
    stub = MagicMock()
    worker._channel = channel
    worker._stub = stub
    return worker, channel, stub


def test_connect_hello_ends_with_a_hello_that_fails_fast() -> None:
    """Once the wait runs out, the last Hello reports why the channel is not ready."""
    worker, _channel, stub = _worker_with_channel()
    stub.Hello.side_effect = _unreachable_hello

    with (
        patch('dapr.ext.workflow._durabletask.worker._CONNECT_HELLO_TIMEOUT', 0.35),
        patch('dapr.ext.workflow._durabletask.worker._CONNECT_HELLO_STEP_TIMEOUT', 0.1),
        pytest.raises(_RpcError) as raised,
    ):
        worker._send_connect_hello()

    assert raised.value.code() == grpc.StatusCode.UNAVAILABLE
    waits_for_ready = [call.kwargs['wait_for_ready'] for call in stub.Hello.call_args_list]
    assert waits_for_ready[-1] is False
    assert len(waits_for_ready) > 1
    assert all(waits_for_ready[:-1])


def test_connect_hello_does_not_retry_a_refusal() -> None:
    """Only a timed-out Hello is retried; any other answer from the sidecar is final."""
    worker, _channel, stub = _worker_with_channel()
    stub.Hello.side_effect = _RpcError(grpc.StatusCode.UNAUTHENTICATED)

    with pytest.raises(_RpcError) as raised:
        worker._send_connect_hello()

    assert raised.value.code() == grpc.StatusCode.UNAUTHENTICATED
    stub.Hello.assert_called_once()


def test_connect_hello_fails_once_the_channel_is_closed() -> None:
    worker, _channel, stub = _worker_with_channel()
    worker._close_channel()

    with pytest.raises(RuntimeError, match='the worker is stopping'):
        worker._send_connect_hello()

    stub.Hello.assert_not_called()


def test_result_is_dropped_once_the_channel_is_closed() -> None:
    worker, _channel, stub = _worker_with_channel()
    worker._close_channel()

    worker._deliver_activity_response(pb.ActivityRequest(), pb.ActivityResponse(), '', 'instance')

    stub.CompleteActivityTask.assert_not_called()
    with worker._sidecar_stub() as handed_out:
        assert handed_out is None


def test_channel_is_closed_only_after_the_calls_in_flight_on_it() -> None:
    """Closing early could land between a holder's two calls, and the second would crash."""
    worker, channel, _stub = _worker_with_channel()

    with worker._sidecar_stub() as stub:
        assert stub is not None
        closer = threading.Thread(target=worker._close_channel)
        closer.start()
        closer.join(0.2)
        assert closer.is_alive()
        channel.close.assert_not_called()

    closer.join(5)
    channel.close.assert_called_once()


def test_stop_closes_the_channel_after_a_call_in_flight_finishes() -> None:
    worker, channel, _stub = _worker_with_channel()
    release = threading.Event()
    call_started = threading.Event()

    def held_call() -> None:
        with worker._sidecar_stub():
            call_started.set()
            release.wait(5)

    caller = threading.Thread(target=held_call)
    caller.start()
    assert call_started.wait(5)
    with patch('dapr.ext.workflow._durabletask.worker._STOP_DRAIN_TIMEOUT', 0.1):
        stopper = threading.Thread(target=worker.stop)
        stopper.start()
        stopper.join(0.5)
    assert stopper.is_alive(), 'stop() closed the channel under a call in flight'
    channel.close.assert_not_called()

    release.set()
    caller.join(5)
    stopper.join(5)
    channel.close.assert_called_once()


def test_result_ready_while_the_worker_stops_is_still_delivered() -> None:
    worker, _channel, stub = _worker_with_channel()
    release = threading.Event()
    call_started = threading.Event()

    def held_call() -> None:
        with worker._sidecar_stub():
            call_started.set()
            release.wait(5)

    caller = threading.Thread(target=held_call)
    caller.start()
    assert call_started.wait(5)
    stopper = threading.Thread(target=worker.stop)
    stopper.start()
    assert _wait_until(worker._shutdown.is_set)

    worker._deliver_activity_response(pb.ActivityRequest(), pb.ActivityResponse(), '', 'instance')
    release.set()
    caller.join(5)
    stopper.join(10)

    stub.CompleteActivityTask.assert_called_once()
