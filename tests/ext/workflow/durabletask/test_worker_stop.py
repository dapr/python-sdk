import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import grpc
import pytest

from dapr.ext.workflow._durabletask.worker import TaskHubGrpcWorker


# Helper to create a running worker with a mocked runLoop
def _make_running_worker():
    worker = TaskHubGrpcWorker()
    worker._is_running = True
    worker._runLoop = MagicMock()
    worker._runLoop.is_alive.return_value = False
    return worker


def test_stop_with_grpc_future():
    """stop() cancels the work-item stream and closes the channel."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._channel = mock_channel
    worker._response_stream = MagicMock(spec=grpc.Future)
    worker.stop()
    mock_channel.close.assert_called_once()


def test_stop_with_generator_call():
    """stop() closes the channel even when response stream has a .call attribute."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._channel = mock_channel
    mock_stream = MagicMock()
    mock_stream.call = MagicMock()
    worker._response_stream = mock_stream
    worker.stop()
    mock_channel.close.assert_called_once()


def test_stop_with_unknown_stream_type():
    """stop() closes the channel regardless of response stream type."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._channel = mock_channel
    worker._response_stream = object()
    worker.stop()
    mock_channel.close.assert_called_once()


def test_stop_with_none_stream():
    worker = _make_running_worker()
    worker._response_stream = None
    worker._channel = None
    # Should not raise
    worker.stop()


def test_stop_when_not_running():
    worker = TaskHubGrpcWorker()
    worker._is_running = False
    # Should return immediately, not set _shutdown
    with patch.object(worker._shutdown, 'set') as shutdown_set:
        worker.stop()
        shutdown_set.assert_not_called()


def test_stop_channel_close_handles_exception(caplog):
    """stop() handles exceptions from channel.close() gracefully."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    mock_channel.close.side_effect = Exception('close failed')
    worker._channel = mock_channel
    # Should not raise
    worker.stop()
    assert worker._channel is None


def test_stop_warns_when_the_run_loop_outlives_the_timeout(caplog):
    """stop() still finishes when the worker thread does not exit in time, and says so."""
    worker = _make_running_worker()
    worker._channel = MagicMock()
    worker._runLoop.is_alive.return_value = True
    worker.stop()
    assert 'did not complete within' in caplog.text
    assert worker._runLoop is None


def test_stop_before_start_is_noop():
    """stop() is safe to call before start() — _runLoop is None, no AttributeError."""
    worker = TaskHubGrpcWorker()
    with patch.object(worker._shutdown, 'set') as shutdown_set:
        worker.stop()
        shutdown_set.assert_not_called()


def test_stop_is_idempotent():
    """A second stop() returns early because _runLoop was cleared by the first."""
    worker = _make_running_worker()
    worker._channel = MagicMock()
    worker.stop()
    assert worker._runLoop is None
    with patch.object(worker._shutdown, 'set') as shutdown_set:
        worker.stop()
        shutdown_set.assert_not_called()


def test_start_raises_when_run_loop_exits_early():
    """start() raises RuntimeError if the run loop thread exits before _stream_ready is set."""
    worker = TaskHubGrpcWorker()

    async def fast_exit():
        return

    with patch.object(worker, '_async_run_loop', side_effect=fast_exit):
        with pytest.raises(RuntimeError, match='Worker run loop exited'):
            worker.start()


def test_start_raises_when_stopped_during_startup():
    """stop() unblocks a start() that is waiting for _stream_ready; start() raises."""
    worker = TaskHubGrpcWorker()

    async def wait_for_shutdown():
        # Block without setting _stream_ready so start() stays in its wait loop.
        while not worker._shutdown.is_set():
            await asyncio.sleep(0.05)

    errors = []

    def _start():
        try:
            worker.start()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    with patch.object(worker, '_async_run_loop', side_effect=wait_for_shutdown):
        t = threading.Thread(target=_start)
        t.start()
        # Let start() enter its wait loop (timeout=1 per iteration).
        time.sleep(1.2)
        worker.stop()
        t.join(timeout=5)

    assert not t.is_alive(), 'start() did not return after stop()'
    assert len(errors) == 1, f'Expected exactly one error, got: {errors}'
    assert isinstance(errors[0], RuntimeError)
    assert 'Worker was stopped' in str(errors[0])
