from unittest.mock import MagicMock, patch

import grpc

from durabletask.worker import TaskHubGrpcWorker


# Helper to create a running worker with a mocked runLoop
def _make_running_worker():
    worker = TaskHubGrpcWorker()
    worker._is_running = True
    worker._runLoop = MagicMock()
    worker._runLoop.is_alive.return_value = False
    return worker


def test_stop_with_grpc_future():
    """stop() closes the channel, which propagates cancellation to all streams."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._current_channel = mock_channel
    worker._response_stream = MagicMock(spec=grpc.Future)
    worker.stop()
    mock_channel.close.assert_called_once()


def test_stop_with_generator_call():
    """stop() closes the channel even when response stream has a .call attribute."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._current_channel = mock_channel
    mock_stream = MagicMock()
    mock_stream.call = MagicMock()
    worker._response_stream = mock_stream
    worker.stop()
    mock_channel.close.assert_called_once()


def test_stop_with_unknown_stream_type():
    """stop() closes the channel regardless of response stream type."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._current_channel = mock_channel
    worker._response_stream = object()
    worker.stop()
    mock_channel.close.assert_called_once()


def test_stop_with_none_stream():
    worker = _make_running_worker()
    worker._response_stream = None
    worker._current_channel = None
    # Should not raise
    worker.stop()


def test_stop_when_not_running():
    worker = TaskHubGrpcWorker()
    worker._is_running = False
    # Should return immediately, not set _shutdown
    with patch.object(worker._shutdown, "set") as shutdown_set:
        worker.stop()
        shutdown_set.assert_not_called()


def test_stop_channel_close_handles_exception(caplog):
    """stop() handles exceptions from channel.close() gracefully."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    mock_channel.close.side_effect = Exception("close failed")
    worker._current_channel = mock_channel
    # Should not raise
    worker.stop()
    assert worker._current_channel is None


def test_deferred_channel_close_waits_then_closes():
    """_schedule_deferred_channel_close waits grace period, then closes old channel."""
    worker = TaskHubGrpcWorker()
    old_channel = MagicMock()

    worker._schedule_deferred_channel_close(old_channel, grace_timeout=0.1)
    # Thread should be tracked
    assert len(worker._channel_cleanup_threads) == 1

    # Wait for the grace period to expire and the thread to finish
    worker._channel_cleanup_threads[0].join(timeout=2)
    old_channel.close.assert_called_once()


def test_deferred_channel_close_fires_immediately_on_shutdown():
    """Deferred close returns immediately when shutdown is already set."""
    worker = TaskHubGrpcWorker()
    worker._shutdown.set()
    old_channel = MagicMock()

    worker._schedule_deferred_channel_close(old_channel, grace_timeout=60)
    # Even with a 60s grace, shutdown makes it return immediately
    worker._channel_cleanup_threads[0].join(timeout=2)
    old_channel.close.assert_called_once()


def test_deferred_channel_close_handles_close_exception():
    """Deferred close handles exceptions from channel.close() gracefully."""
    worker = TaskHubGrpcWorker()
    worker._shutdown.set()
    old_channel = MagicMock()
    old_channel.close.side_effect = Exception("already closed")

    # Should not raise
    worker._schedule_deferred_channel_close(old_channel, grace_timeout=0)
    worker._channel_cleanup_threads[0].join(timeout=2)
    old_channel.close.assert_called_once()


def test_stop_joins_deferred_cleanup_threads():
    """stop() joins all deferred channel cleanup threads."""
    worker = _make_running_worker()
    mock_channel = MagicMock()
    worker._current_channel = mock_channel

    # Pre-populate a cleanup thread (simulating a prior reconnection)
    old_channel = MagicMock()
    worker._schedule_deferred_channel_close(old_channel, grace_timeout=60)
    assert len(worker._channel_cleanup_threads) == 1

    worker.stop()
    # stop() sets shutdown, which unblocks deferred close threads
    # After stop(), cleanup threads list should be cleared
    assert len(worker._channel_cleanup_threads) == 0
    old_channel.close.assert_called_once()
    mock_channel.close.assert_called_once()


def test_deferred_close_prunes_finished_threads():
    """_schedule_deferred_channel_close prunes already-finished threads."""
    worker = TaskHubGrpcWorker()
    worker._shutdown.set()  # Make threads complete immediately

    ch1 = MagicMock()
    ch2 = MagicMock()
    worker._schedule_deferred_channel_close(ch1, grace_timeout=0)
    worker._channel_cleanup_threads[0].join(timeout=2)

    # ch1's thread is finished; scheduling ch2 should prune it
    worker._schedule_deferred_channel_close(ch2, grace_timeout=0)
    worker._channel_cleanup_threads[-1].join(timeout=2)
    # Only the still-alive (or just-finished ch2) thread remains; ch1's was pruned
    assert len(worker._channel_cleanup_threads) <= 1
