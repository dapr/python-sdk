# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import contextlib
import inspect
import logging
import os
import random
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event, Thread
from types import GeneratorType
from typing import Any, Generator, Iterator, Optional, Sequence, TypeVar, Union

import grpc
from google.protobuf import empty_pb2

import durabletask.internal.helpers as ph
import durabletask.internal.orchestrator_service_pb2 as pb
import durabletask.internal.orchestrator_service_pb2_grpc as stubs
import durabletask.internal.shared as shared
from durabletask import deterministic, task
from durabletask.internal.grpc_interceptor import DefaultClientInterceptorImpl

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")

# If `opentelemetry-sdk` is available, enable the tracer
try:
    from opentelemetry import trace
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    otel_propagator = TraceContextTextMapPropagator()
    otel_tracer = trace.get_tracer(__name__)
except ImportError:
    otel_tracer = None


class VersionNotRegisteredException(Exception):
    pass


def _log_all_threads(logger: logging.Logger, context: str = ""):
    """Helper function to log all currently active threads for debugging."""
    active_threads = threading.enumerate()
    thread_info = []
    for t in active_threads:
        thread_info.append(
            f"name='{t.name}', id={t.ident}, daemon={t.daemon}, alive={t.is_alive()}"
        )
    logger.debug(
        f"[THREAD_TRACE] {context} Active threads ({len(active_threads)}): {', '.join(thread_info)}"
    )


class ConcurrencyOptions:
    """Configuration options for controlling concurrency of different work item types and the thread pool size.

    This class provides fine-grained control over concurrent processing limits for
    activities, orchestrations and the thread pool size.
    """

    def __init__(
        self,
        maximum_concurrent_activity_work_items: Optional[int] = None,
        maximum_concurrent_orchestration_work_items: Optional[int] = None,
        maximum_thread_pool_workers: Optional[int] = None,
    ):
        """Initialize concurrency options.

        Args:
            maximum_concurrent_activity_work_items: Maximum number of activity work items
                that can be processed concurrently. Defaults to 100 * processor_count.
            maximum_concurrent_orchestration_work_items: Maximum number of orchestration work items
                that can be processed concurrently. Defaults to 100 * processor_count.
            maximum_thread_pool_workers: Maximum number of thread pool workers to use.
        """
        processor_count = os.cpu_count() or 1
        default_concurrency = 100 * processor_count
        # see https://docs.python.org/3/library/concurrent.futures.html
        default_max_workers = processor_count + 4

        self.maximum_concurrent_activity_work_items = (
            maximum_concurrent_activity_work_items
            if maximum_concurrent_activity_work_items is not None
            else default_concurrency
        )

        self.maximum_concurrent_orchestration_work_items = (
            maximum_concurrent_orchestration_work_items
            if maximum_concurrent_orchestration_work_items is not None
            else default_concurrency
        )

        self.maximum_thread_pool_workers = (
            maximum_thread_pool_workers
            if maximum_thread_pool_workers is not None
            else default_max_workers
        )


class _Registry:
    orchestrators: dict[str, task.Orchestrator]
    versioned_orchestrators: dict[str, dict[str, task.Orchestrator]]
    latest_versioned_orchestrators_version_name: dict[str, str]
    activities: dict[str, task.Activity]

    def __init__(self):
        self.orchestrators = {}
        self.versioned_orchestrators = {}
        self.latest_versioned_orchestrators_version_name = {}
        self.activities = {}

    def add_orchestrator(
        self, fn: task.Orchestrator, version_name: Optional[str] = None, is_latest: bool = False
    ) -> str:
        if fn is None:
            raise ValueError("An orchestrator function argument is required.")

        name = task.get_name(fn)
        self.add_named_orchestrator(name, fn, version_name, is_latest)
        return name

    def add_named_orchestrator(
        self,
        name: str,
        fn: task.Orchestrator,
        version_name: Optional[str] = None,
        is_latest: bool = False,
    ) -> None:
        if not name:
            raise ValueError("A non-empty orchestrator name is required.")

        if version_name is None:
            if name in self.orchestrators:
                raise ValueError(f"A '{name}' orchestrator already exists.")
            self.orchestrators[name] = fn
        else:
            if name not in self.versioned_orchestrators:
                self.versioned_orchestrators[name] = {}
            if version_name in self.versioned_orchestrators[name]:
                raise ValueError(
                    f"The version '{version_name}' of '{name}' orchestrator already exists."
                )
            self.versioned_orchestrators[name][version_name] = fn
            if is_latest:
                self.latest_versioned_orchestrators_version_name[name] = version_name

    def get_orchestrator(
        self, name: str, version_name: Optional[str] = None
    ) -> Optional[tuple[task.Orchestrator, str]]:
        if name in self.orchestrators:
            return self.orchestrators.get(name), None

        if name in self.versioned_orchestrators:
            if version_name:
                version_to_use = version_name
            elif name in self.latest_versioned_orchestrators_version_name:
                version_to_use = self.latest_versioned_orchestrators_version_name[name]
            else:
                return None, None

            if version_to_use not in self.versioned_orchestrators[name]:
                raise VersionNotRegisteredException
            return self.versioned_orchestrators[name].get(version_to_use), version_to_use

        return None, None

    def add_activity(self, fn: task.Activity) -> str:
        if fn is None:
            raise ValueError("An activity function argument is required.")

        name = task.get_name(fn)
        self.add_named_activity(name, fn)
        return name

    def add_named_activity(self, name: str, fn: task.Activity) -> None:
        if not name:
            raise ValueError("A non-empty activity name is required.")
        if name in self.activities:
            raise ValueError(f"A '{name}' activity already exists.")

        self.activities[name] = fn

    def get_activity(self, name: str) -> Optional[task.Activity]:
        return self.activities.get(name)


class OrchestratorNotRegisteredError(ValueError):
    """Raised when attempting to start an orchestration that is not registered"""

    pass


class ActivityNotRegisteredError(ValueError):
    """Raised when attempting to call an activity that is not registered"""

    pass


def _is_message_too_large(rpc_error: grpc.RpcError) -> bool:
    """Return True if the gRPC error is RESOURCE_EXHAUSTED.

    All RESOURCE_EXHAUSTED errors are treated as a permanent message-size violation
    so the sidecar always receives an acknowledgment and avoids infinite redelivery.
    """
    return rpc_error.code() == grpc.StatusCode.RESOURCE_EXHAUSTED


# TODO: refactor this to closely match durabletask-go/client/worker_grpc.go instead of this.
class TaskHubGrpcWorker:
    """A gRPC-based worker for processing durable task orchestrations and activities.

    This worker connects to a Durable Task backend service via gRPC to receive and process
    work items including orchestration functions and activity functions. It provides
    concurrent execution capabilities with configurable limits and automatic retry handling.

    The worker manages the complete lifecycle:
    - Registers orchestrator and activity functions
    - Connects to the gRPC backend service
    - Receives work items and executes them concurrently
    - Handles failures, retries, and state management
    - Provides logging and monitoring capabilities

    Args:
        host_address (Optional[str], optional): The gRPC endpoint address of the backend service.
            Defaults to the value from environment variables or localhost.
        metadata (Optional[list[tuple[str, str]]], optional): gRPC metadata to include with
            requests. Used for authentication and routing. Defaults to None.
        log_handler (optional): Custom logging handler for worker logs. Defaults to None.
        log_formatter (Optional[logging.Formatter], optional): Custom log formatter.
            Defaults to None.
        secure_channel (bool, optional): Whether to use a secure gRPC channel (TLS).
            Defaults to False.
        interceptors (Optional[Sequence[shared.ClientInterceptor]], optional): Custom gRPC
            interceptors to apply to the channel. Defaults to None.
        concurrency_options (Optional[ConcurrencyOptions], optional): Configuration for
            controlling worker concurrency limits. If None, default settings are used.
        stop_timeout (float, optional): Maximum time in seconds to wait for the worker thread
            to stop when calling stop(). Defaults to 30.0. Useful to set lower values in tests.
        keepalive_interval (float, optional): Interval in seconds between application-level
            keepalive Hello RPCs sent to prevent L7 load balancers (e.g. AWS ALB) from closing
            idle HTTP/2 connections. Set to 0 or negative to disable. Defaults to 30.0.

    Attributes:
        concurrency_options (ConcurrencyOptions): The current concurrency configuration.

    Example:
        Basic worker setup:

        >>> from durabletask.worker import TaskHubGrpcWorker, ConcurrencyOptions
        >>>
        >>> # Create worker with custom concurrency settings
        >>> concurrency = ConcurrencyOptions(
        ...     maximum_concurrent_activity_work_items=50,
        ...     maximum_concurrent_orchestration_work_items=20
        ... )
        >>> worker = TaskHubGrpcWorker(
        ...     host_address="localhost:4001",
        ...     concurrency_options=concurrency
        ... )
        >>>
        >>> # Register functions
        >>> @worker.add_orchestrator
        ... def my_orchestrator(context, input):
        ...     result = yield context.call_activity("my_activity", input="hello")
        ...     return result
        >>>
        >>> @worker.add_activity
        ... def my_activity(context, input):
        ...     return f"Processed: {input}"
        >>>
        >>> # Start the worker
        >>> worker.start()
        >>> # ... worker runs in background thread
        >>> worker.stop()

        Using as context manager:

        >>> with TaskHubGrpcWorker() as worker:
        ...     worker.add_orchestrator(my_orchestrator)
        ...     worker.add_activity(my_activity)
        ...     worker.start()
        ...     # Worker automatically stops when exiting context

    Raises:
        RuntimeError: If attempting to add orchestrators/activities while the worker is running,
            or if starting a worker that is already running.
        OrchestratorNotRegisteredError: If an orchestration work item references an
            unregistered orchestrator function.
        ActivityNotRegisteredError: If an activity work item references an unregistered
            activity function.
    """

    _response_stream: Optional[Union[Iterator[grpc.Future], grpc.Future]] = None
    _interceptors: Optional[list[shared.ClientInterceptor]] = None

    def __init__(
        self,
        *,
        host_address: Optional[str] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
        log_handler=None,
        log_formatter: Optional[logging.Formatter] = None,
        secure_channel: bool = False,
        interceptors: Optional[Sequence[shared.ClientInterceptor]] = None,
        concurrency_options: Optional[ConcurrencyOptions] = None,
        channel_options: Optional[Sequence[tuple[str, Any]]] = None,
        stop_timeout: float = 30.0,
        keepalive_interval: float = 30.0,
    ):
        self._registry = _Registry()
        self._host_address = host_address if host_address else shared.get_default_host_address()
        self._logger = shared.get_logger("worker", log_handler, log_formatter)
        self._shutdown = Event()
        self._is_running = False
        self._secure_channel = secure_channel
        self._channel_options = channel_options
        self._stop_timeout = stop_timeout
        self._keepalive_interval = keepalive_interval
        self._current_channel: Optional[grpc.Channel] = None  # Store channel reference for cleanup
        self._channel_cleanup_threads: list[threading.Thread] = []  # Deferred channel close threads
        self._stream_ready = threading.Event()
        # Use provided concurrency options or create default ones
        self._concurrency_options = (
            concurrency_options if concurrency_options is not None else ConcurrencyOptions()
        )

        # Determine the interceptors to use
        if interceptors is not None:
            self._interceptors = list(interceptors)
            if metadata:
                self._interceptors.append(DefaultClientInterceptorImpl(metadata))
        elif metadata:
            self._interceptors = [DefaultClientInterceptorImpl(metadata)]
        else:
            self._interceptors = None

        self._async_worker_manager = _AsyncWorkerManager(self._concurrency_options, self._logger)

    @property
    def concurrency_options(self) -> ConcurrencyOptions:
        """Get the current concurrency options for this worker."""
        return self._concurrency_options

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def add_orchestrator(self, fn: task.Orchestrator) -> str:
        """Registers an orchestrator function with the worker."""
        if self._is_running:
            raise RuntimeError("Orchestrators cannot be added while the worker is running.")
        return self._registry.add_orchestrator(fn)

    def add_activity(self, fn: task.Activity) -> str:
        """Registers an activity function with the worker."""
        if self._is_running:
            raise RuntimeError("Activities cannot be added while the worker is running.")
        return self._registry.add_activity(fn)

    def is_worker_ready(self) -> bool:
        return self._stream_ready.is_set() and self._is_running

    def start(self):
        """Starts the worker on a background thread and begins listening for work items."""
        if self._is_running:
            raise RuntimeError("The worker is already running.")

        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._async_run_loop())

        self._logger.info(f"Starting gRPC worker that connects to {self._host_address}")
        self._runLoop = Thread(target=run_loop, name="WorkerRunLoop")
        self._runLoop.start()
        if not self._stream_ready.wait(timeout=10):
            raise RuntimeError("Failed to establish work item stream connection within 10 seconds")
        self._is_running = True

    async def _keepalive_loop(self, stub):
        """Background keepalive loop to keep the gRPC connection alive through L7 load balancers."""
        loop = asyncio.get_running_loop()
        while not self._shutdown.is_set():
            await asyncio.sleep(self._keepalive_interval)
            if self._shutdown.is_set():
                return
            try:
                await loop.run_in_executor(None, lambda: stub.Hello(empty_pb2.Empty(), timeout=10))
            except Exception as e:
                self._logger.debug(f"keepalive failed: {e}")

    @staticmethod
    async def _cancel_keepalive(keepalive_task):
        """Cancel and await the keepalive task if it exists."""
        if keepalive_task is not None:
            keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keepalive_task

    # TODO: refactor this to be more readable and maintainable.
    async def _async_run_loop(self):
        """
        This is the main async loop that runs the worker.
        It is responsible for:
            - Creating a fresh connection to the sidecar
            - Reading work items from the sidecar
            - Executing the work items
            - Shutting down the worker
        """
        worker_task = asyncio.create_task(self._async_worker_manager.run())
        # Connection state management for retry fix
        current_channel = None
        current_stub = None
        current_reader_thread = None
        conn_retry_count = 0
        conn_max_retry_delay = 15

        def create_fresh_connection():
            nonlocal current_channel, current_stub, conn_retry_count
            # Schedule deferred close of old channel to avoid orphaned TCP
            # connections. In-flight RPCs on the old stub may still reference
            # the channel from another thread, so we wait a grace period
            # before closing instead of closing immediately.
            if current_channel is not None:
                self._schedule_deferred_channel_close(current_channel)
            current_channel = None
            current_stub = None
            try:
                current_channel = shared.get_grpc_channel(
                    self._host_address,
                    self._secure_channel,
                    self._interceptors,
                    options=self._channel_options,
                )
                # Store channel reference for cleanup in stop()
                self._current_channel = current_channel
                current_stub = stubs.TaskHubSidecarServiceStub(current_channel)
                current_stub.Hello(empty_pb2.Empty())
                conn_retry_count = 0
                self._logger.info(f"Created fresh connection to {self._host_address}")
            except Exception as e:
                self._logger.warning(f"Failed to create connection: {e}")
                current_channel = None
                self._current_channel = None
                current_stub = None
                raise

        def invalidate_connection():
            nonlocal current_channel, current_stub, current_reader_thread
            # Schedule deferred close of old channel to avoid orphaned TCP
            # connections. In-flight RPCs (e.g. CompleteActivityTask) may still
            # be using the stub on another thread, so we defer the close by a
            # grace period instead of closing immediately.
            if current_channel is not None:
                self._schedule_deferred_channel_close(current_channel)
            current_channel = None
            self._current_channel = None
            current_stub = None
            self._response_stream = None

            if current_reader_thread is not None:
                current_reader_thread.join(timeout=5)
                current_reader_thread = None

        def should_invalidate_connection(rpc_error):
            error_code = rpc_error.code()  # type: ignore
            connection_level_errors = {
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.CANCELLED,
                grpc.StatusCode.UNAUTHENTICATED,
                grpc.StatusCode.ABORTED,
                grpc.StatusCode.INTERNAL,  # RST_STREAM from proxy means connection is dead
            }
            return error_code in connection_level_errors

        while True:
            if self._shutdown.is_set():
                break
            if current_stub is None:
                try:
                    create_fresh_connection()
                except Exception:
                    conn_retry_count += 1
                    delay = min(
                        conn_max_retry_delay,
                        (2 ** min(conn_retry_count, 6)) + random.uniform(0, 1),
                    )
                    self._logger.warning(
                        f"Connection failed, retrying in {delay:.2f} seconds (attempt {conn_retry_count})"
                    )
                    if self._shutdown.wait(delay):
                        break
                    continue
            keepalive_task = None
            try:
                assert current_stub is not None
                stub = current_stub
                get_work_items_request = pb.GetWorkItemsRequest(
                    maxConcurrentOrchestrationWorkItems=self._concurrency_options.maximum_concurrent_orchestration_work_items,
                    maxConcurrentActivityWorkItems=self._concurrency_options.maximum_concurrent_activity_work_items,
                )
                try:
                    self._response_stream = stub.GetWorkItems(get_work_items_request)
                    self._logger.info(
                        f"Successfully connected to {self._host_address}. Waiting for work items..."
                    )
                except Exception:
                    raise

                # Use a thread to read from the blocking gRPC stream and forward to asyncio
                import queue

                work_item_queue = queue.Queue()
                SHUTDOWN_SENTINEL = None

                # NOTE: This is equivalent to the Durabletask Go goroutine calling stream.Recv() in worker_grpc.go StartWorkItemListener()
                def stream_reader():
                    try:
                        if self._response_stream is None:
                            return
                        stream = self._response_stream

                        # Use next() to allow shutdown check between items
                        # This matches Go's pattern: check ctx.Err() after each stream.Recv()
                        while True:
                            if self._shutdown.is_set():
                                self._logger.debug("Stream reader: shutdown detected, exiting loop")
                                break

                            try:
                                # NOTE: next(stream) blocks until gRPC returns the next work item or cancels the stream.
                                # There is no way to interrupt this blocking call in Python gRPC. When shutdown is
                                # initiated, the channel closure propagates to this call, which can take several seconds.
                                # The thread will exit once gRPC raises grpc.RpcError with StatusCode.CANCELLED.
                                work_item = next(stream)
                                # Check shutdown again after getting item (in case shutdown happened during next())
                                if self._shutdown.is_set():
                                    break
                                work_item_queue.put(work_item)
                            except StopIteration:
                                # stream ended naturally
                                break
                            except grpc.RpcError as rpc_error:
                                # Check if this is due to shutdown/cancellation
                                if (
                                    self._shutdown.is_set()
                                    or rpc_error.code() == grpc.StatusCode.CANCELLED
                                ):
                                    self._logger.debug(
                                        f"Stream reader: stream cancelled during shutdown (code={rpc_error.code()})"
                                    )
                                    break
                                # Other RPC errors - put in queue for async loop to handle
                                self._logger.warning(
                                    "Stream reader: RPC error (code=%s): %s",
                                    rpc_error.code(),
                                    rpc_error.details()
                                    if hasattr(rpc_error, "details")
                                    else rpc_error,
                                )
                                break
                            except Exception as stream_error:
                                # Check if this is due to shutdown
                                if self._shutdown.is_set():
                                    self._logger.debug(
                                        f"Stream reader: exception during shutdown: {type(stream_error).__name__}: {stream_error}"
                                    )
                                    break
                                # Other stream errors - put in queue for async loop to handle
                                self._logger.error(
                                    f"Stream reader: unexpected error: {type(stream_error).__name__}: {stream_error}",
                                    exc_info=True,
                                )
                                raise

                    except Exception as e:
                        self._logger.exception(
                            f"Stream reader: fatal exception in stream_reader: {type(e).__name__}: {e}",
                            exc_info=True,
                        )
                        if not self._shutdown.is_set():
                            try:
                                work_item_queue.put(e)
                            except Exception as queue_error:
                                self._logger.error(
                                    f"Stream reader: failed to put exception in queue: {queue_error}"
                                )
                    finally:
                        # signal that the stream reader is done (ie matching Go's context cancellation)
                        try:
                            work_item_queue.put(SHUTDOWN_SENTINEL)
                        except Exception:
                            # queue might be closed so ignore this
                            pass

                # Use non-daemon thread (daemon=False) to ensure proper resource cleanup.
                # Daemon threads exit immediately when the main program exits, which prevents
                # cleanup of gRPC channel resources and OTel interceptors. Non-daemon threads
                # block shutdown until they complete, ensuring all resources are properly closed.
                current_reader_thread = threading.Thread(
                    target=stream_reader, daemon=False, name="StreamReader"
                )

                try:
                    current_reader_thread.start()
                    self._stream_ready.set()
                except Exception:
                    raise

                loop = asyncio.get_running_loop()
                if self._keepalive_interval > 0:
                    keepalive_task = asyncio.ensure_future(self._keepalive_loop(stub))

                # NOTE: This is a blocking call that will wait for a work item to become available or the shutdown sentinel
                while not self._shutdown.is_set():
                    try:
                        # Use timeout to allow shutdown check (mimicing Go's select with ctx.Done())
                        work_item = await loop.run_in_executor(
                            None, lambda: work_item_queue.get(timeout=0.1)
                        )
                        # Essentially check for ctx.Done() in Go
                        if work_item == SHUTDOWN_SENTINEL:
                            break

                        if self._async_worker_manager._shutdown or loop.is_closed():
                            self._logger.debug(
                                "Async worker manager shut down or loop closed, exiting work item processing"
                            )
                            break
                        if isinstance(work_item, Exception):
                            raise work_item
                        request_type = work_item.WhichOneof("request")
                        self._logger.debug(f'Received "{request_type}" work item')
                        if work_item.HasField("orchestratorRequest"):
                            self._async_worker_manager.submit_orchestration(
                                self._execute_orchestrator,
                                work_item.orchestratorRequest,
                                stub,
                                work_item.completionToken,
                            )
                        elif work_item.HasField("activityRequest"):
                            self._async_worker_manager.submit_activity(
                                self._execute_activity,
                                work_item.activityRequest,
                                stub,
                                work_item.completionToken,
                            )
                        elif work_item.HasField("healthPing"):
                            pass
                        else:
                            self._logger.warning(f"Unexpected work item type: {request_type}")
                    except queue.Empty:
                        continue
                    except grpc.RpcError:
                        raise  # let it be captured/parsed by outer except and avoid noisy log
                    except Exception as e:
                        if self._async_worker_manager._shutdown or loop.is_closed():
                            break
                        invalidate_connection()
                        raise e
                current_reader_thread.join(timeout=1)
                await self._cancel_keepalive(keepalive_task)

                if self._shutdown.is_set():
                    self._logger.info(f"Disconnected from {self._host_address}")
                    break

                # Stream ended without shutdown being requested - reconnect
                self._logger.info(
                    f"Work item stream ended. Will attempt to reconnect to {self._host_address}..."
                )
                invalidate_connection()
                # Fall through to the top of the outer loop, which will
                # create a fresh connection (with retry/backoff if needed)
            except grpc.RpcError as rpc_error:
                await self._cancel_keepalive(keepalive_task)
                # Check shutdown first - if shutting down, exit immediately
                if self._shutdown.is_set():
                    self._logger.debug("Shutdown detected during RPC error handling, exiting")
                    break
                should_invalidate = should_invalidate_connection(rpc_error)
                if should_invalidate:
                    invalidate_connection()
                error_code = rpc_error.code()  # type: ignore
                error_detail = (
                    rpc_error.details() if hasattr(rpc_error, "details") else str(rpc_error)
                )

                if error_code == grpc.StatusCode.CANCELLED:
                    self._logger.info(f"Disconnected from {self._host_address}")
                    break
                elif should_invalidate:
                    self._logger.warning(
                        f"Connection error ({error_code}): {error_detail} — resetting connection"
                    )
                else:
                    self._logger.warning(f"gRPC error ({error_code}): {error_detail}")
            except RuntimeError as ex:
                await self._cancel_keepalive(keepalive_task)
                # RuntimeError often indicates asyncio loop issues (e.g., "cannot schedule new futures after shutdown")
                # Check shutdown state first
                if self._shutdown.is_set():
                    self._logger.debug(
                        f"Shutdown detected during RuntimeError handling, exiting: {ex}"
                    )
                    break
                # Check if async worker manager is shut down or loop is closed
                try:
                    loop = asyncio.get_running_loop()
                    if self._async_worker_manager._shutdown or loop.is_closed():
                        self._logger.debug(
                            f"Async worker manager shut down or loop closed, exiting: {ex}"
                        )
                        break
                except RuntimeError:
                    # No event loop running, treat as shutdown
                    self._logger.debug(f"No event loop running, exiting: {ex}")
                    break
                # If we can't get the loop or it's in a bad state, and we got a RuntimeError,
                # it's likely shutdown-related. Break to prevent infinite retries.
                break
            except Exception as ex:
                await self._cancel_keepalive(keepalive_task)
                if self._shutdown.is_set():
                    self._logger.debug(
                        f"Shutdown detected during exception handling, exiting: {ex}"
                    )
                    break
                # Check if async worker manager is shut down or loop is closed
                try:
                    loop = asyncio.get_running_loop()
                    if self._async_worker_manager._shutdown or loop.is_closed():
                        self._logger.debug(
                            f"Async worker manager shut down or loop closed, exiting: {ex}"
                        )
                        break
                except RuntimeError:
                    # No event loop running, treat as shutdown
                    self._logger.debug(f"No event loop running, exiting: {ex}")
                    break
                invalidate_connection()
                self._logger.warning(f"Unexpected error: {ex}")
        invalidate_connection()
        self._logger.info("No longer listening for work items")

        # Cancel worker_task to ensure shutdown completes even if tasks are still running
        worker_task.cancel()
        try:
            # Wait for cancellation to complete, with a timeout to prevent indefinite waiting
            await asyncio.wait_for(worker_task, timeout=5.0)
        except asyncio.CancelledError:
            self._logger.debug("Worker task cancelled during shutdown")
        except asyncio.TimeoutError:
            self._logger.warning("Worker task did not complete within timeout during shutdown")
        except Exception as e:
            self._logger.warning(f"Error while waiting for worker task shutdown: {e}")

    def _schedule_deferred_channel_close(
        self, old_channel: grpc.Channel, grace_timeout: float = 10.0
    ):
        """Schedule a deferred close of an old gRPC channel.

        Waits up to *grace_timeout* seconds for in-flight RPCs to complete
        before closing the channel.  This prevents orphaned TCP connections
        while still allowing in-flight work (e.g. ``CompleteActivityTask``
        calls on another thread) to finish gracefully.

        During ``stop()``, ``_shutdown`` is already set so the wait returns
        immediately and the channel is closed at once.
        """
        # Prune already-finished cleanup threads to avoid unbounded growth
        self._channel_cleanup_threads = [t for t in self._channel_cleanup_threads if t.is_alive()]

        def _deferred_close():
            try:
                # Normal reconnect: wait grace period for RPCs to drain.
                # Shutdown: _shutdown is already set, returns immediately.
                self._shutdown.wait(timeout=grace_timeout)
            finally:
                try:
                    old_channel.close()
                    self._logger.debug("Deferred channel close completed")
                except Exception as e:
                    self._logger.debug(f"Error during deferred channel close: {e}")

        thread = threading.Thread(target=_deferred_close, daemon=True, name="ChannelCleanup")
        thread.start()
        self._channel_cleanup_threads.append(thread)

    def stop(self):
        """Stops the worker and waits for any pending work items to complete."""
        if not self._is_running:
            return

        self._logger.info("Stopping gRPC worker...")
        self._shutdown.set()
        # Close the channel — propagates cancellation to all streams and cleans up resources
        if self._current_channel is not None:
            try:
                self._current_channel.close()
            except Exception as e:
                self._logger.exception(f"Error closing gRPC channel: {e}")
            finally:
                self._current_channel = None

        if self._runLoop is not None:
            self._runLoop.join(timeout=self._stop_timeout)
            if self._runLoop.is_alive():
                self._logger.warning(
                    f"Worker thread did not complete within {self._stop_timeout}s timeout. "
                    "Some resources may not be fully cleaned up."
                )
            else:
                self._logger.debug("Worker thread completed successfully")

        # Wait for any deferred channel-cleanup threads to finish
        for t in self._channel_cleanup_threads:
            t.join(timeout=5)
        self._channel_cleanup_threads.clear()

        self._async_worker_manager.shutdown()
        self._logger.info("Worker shutdown completed")
        self._is_running = False

    # TODO: This should be removed in the future as we do handle grpc errs
    def _handle_grpc_execution_error(self, rpc_error: grpc.RpcError, request_type: str):
        """Handle a gRPC execution error during shutdown or connection reset."""
        details = str(rpc_error).lower()
        # These errors are transient — the sidecar will re-dispatch the work item.
        transient_errors = {
            grpc.StatusCode.CANCELLED,
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.UNKNOWN,
            grpc.StatusCode.INTERNAL,
        }
        is_transient = rpc_error.code() in transient_errors
        is_benign = (
            "unknown instance id/task id combo" in details
            or "channel closed" in details
            or "locally cancelled by application" in details
        )
        if is_transient or is_benign or self._shutdown.is_set():
            self._logger.warning(
                f"Could not deliver {request_type} result ({rpc_error.code()}): "
                f"{rpc_error.details() if hasattr(rpc_error, 'details') else rpc_error} — sidecar will re-dispatch"
            )
        else:
            self._logger.exception(f"Failed to deliver {request_type} result: {rpc_error}")

    def _execute_orchestrator(
        self,
        req: pb.OrchestratorRequest,
        stub: stubs.TaskHubSidecarServiceStub,
        completionToken,
    ):
        try:
            executor = _OrchestrationExecutor(self._registry, self._logger)
            result = executor.execute(req.instanceId, req.pastEvents, req.newEvents)

            version = None
            if result.version_name:
                version = version or pb.OrchestrationVersion()
                version.name = result.version_name
            if result.patches:
                version = version or pb.OrchestrationVersion()
                version.patches.extend(result.patches)

            res = pb.OrchestratorResponse(
                instanceId=req.instanceId,
                actions=result.actions,
                customStatus=ph.get_string_value(result.encoded_custom_status),
                completionToken=completionToken,
                version=version,
            )
        except Exception as ex:
            self._logger.exception(
                f"An error occurred while trying to execute instance '{req.instanceId}': {ex}"
            )
            failure_details = ph.new_failure_details(ex)
            actions = [
                ph.new_complete_orchestration_action(
                    -1, pb.ORCHESTRATION_STATUS_FAILED, "", failure_details
                )
            ]
            res = pb.OrchestratorResponse(
                instanceId=req.instanceId,
                actions=actions,
                completionToken=completionToken,
            )

        try:
            stub.CompleteOrchestratorTask(res)
        except grpc.RpcError as rpc_error:  # type: ignore
            if _is_message_too_large(rpc_error):
                # Response is too large to deliver - fail the orchestration immediately.
                # This can only be fixed with infrastructure changes (increasing gRPC max message size).
                self._logger.error(
                    f"Orchestrator response for '{req.instanceId}' is too large to deliver "
                    f"(RESOURCE_EXHAUSTED). Failing the orchestration task: {rpc_error.details()}"
                )
                failure_actions = [
                    ph.new_complete_orchestration_action(
                        -1, pb.ORCHESTRATION_STATUS_FAILED, "",
                        ph.new_failure_details(RuntimeError(
                            f"Orchestrator response exceeds gRPC max message size: {rpc_error.details()}"
                        ))
                    )
                ]
                failure_res = pb.OrchestratorResponse(
                    instanceId=req.instanceId,
                    actions=failure_actions,
                    completionToken=completionToken,
                )
                try:
                    stub.CompleteOrchestratorTask(failure_res)
                except Exception as ex:
                    self._logger.exception(
                        f"Failed to deliver orchestrator failure response for '{req.instanceId}': {ex}"
                    )
            else:
                self._handle_grpc_execution_error(rpc_error, "orchestrator")
        except ValueError:
            # gRPC raises ValueError when the underlying channel has been closed (e.g. during reconnection).
            self._logger.debug(
                f"Could not deliver orchestrator response for '{req.instanceId}': "
                f"channel was closed (likely due to reconnection). "
                f"The sidecar will re-dispatch this work item."
            )
        except Exception as ex:
            self._logger.exception(
                f"Failed to deliver orchestrator response for '{req.instanceId}' to sidecar: {ex}"
            )

    def _execute_activity(
        self,
        req: pb.ActivityRequest,
        stub: stubs.TaskHubSidecarServiceStub,
        completionToken,
    ):
        instance_id = req.orchestrationInstance.instanceId

        if otel_tracer is not None:
            span_context = otel_tracer.start_as_current_span(
                name=f"activity: {req.name}",
                context=otel_propagator.extract(
                    carrier={"traceparent": req.parentTraceContext.traceParent}
                ),
                attributes={
                    "durabletask.task.instance_id": instance_id,
                    "durabletask.task.id": req.taskId,
                    "durabletask.activity.name": req.name,
                },
            )
        else:
            span_context = contextlib.nullcontext()

        with span_context:
            try:
                executor = _ActivityExecutor(self._registry, self._logger)
                result = executor.execute(
                    instance_id, req.name, req.taskId, req.input.value, req.taskExecutionId
                )
                res = pb.ActivityResponse(
                    instanceId=instance_id,
                    taskId=req.taskId,
                    result=ph.get_string_value(result),
                    completionToken=completionToken,
                )
            except Exception as ex:
                res = pb.ActivityResponse(
                    instanceId=instance_id,
                    taskId=req.taskId,
                    failureDetails=ph.new_failure_details(ex),
                    completionToken=completionToken,
                )

            try:
                stub.CompleteActivityTask(res)
            except grpc.RpcError as rpc_error:  # type: ignore
                if _is_message_too_large(rpc_error):
                    # Result is too large to deliver - fail the activity immediately.
                    # This can only be fixed with infrastructure changes (increasing gRPC max message size).
                    self._logger.error(
                        f"Activity '{req.name}#{req.taskId}' result is too large to deliver "
                        f"(RESOURCE_EXHAUSTED). Failing the activity task: {rpc_error.details()}"
                    )
                    failure_res = pb.ActivityResponse(
                        instanceId=instance_id,
                        taskId=req.taskId,
                        failureDetails=ph.new_failure_details(RuntimeError(
                            f"Activity result exceeds gRPC max message size: {rpc_error.details()}"
                        )),
                        completionToken=completionToken,
                    )
                    try:
                        stub.CompleteActivityTask(failure_res)
                    except Exception as ex:
                        self._logger.exception(
                            f"Failed to deliver activity failure response for '{req.name}#{req.taskId}' "
                            f"of orchestration ID '{instance_id}': {ex}"
                        )
                else:
                    self._handle_grpc_execution_error(rpc_error, "activity")
            except ValueError:
                # gRPC raises ValueError when the underlying channel has been closed (e.g. during reconnection).
                self._logger.debug(
                    f"Could not deliver activity response for '{req.name}#{req.taskId}' of "
                    f"orchestration ID '{instance_id}': channel was closed (likely due to "
                    f"reconnection). The sidecar will re-dispatch this work item."
                )
            except Exception as ex:
                self._logger.exception(
                    f"Failed to deliver activity response for '{req.name}#{req.taskId}' of orchestration ID '{instance_id}' to sidecar: {ex}"
                )


class _RuntimeOrchestrationContext(
    task.OrchestrationContext, deterministic.DeterministicContextMixin
):
    _generator: Optional[Generator[task.Task, Any, Any]]
    _previous_task: Optional[task.Task]

    def __init__(self, instance_id: str):
        super().__init__()
        self._generator = None
        self._is_replaying = True
        self._is_complete = False
        self._result = None
        self._pending_actions: dict[int, pb.OrchestratorAction] = {}
        self._pending_tasks: dict[int, task.CompletableTask] = {}
        self._sequence_number = 0
        self._current_utc_datetime = datetime(1000, 1, 1)
        self._instance_id = instance_id
        self._app_id = None
        self._completion_status: Optional[pb.OrchestrationStatus] = None
        self._received_events: dict[str, list[Any]] = {}
        self._pending_events: dict[str, list[task.CompletableTask]] = {}
        self._new_input: Optional[Any] = None
        self._save_events = False
        self._encoded_custom_status: Optional[str] = None
        self._orchestrator_version_name: Optional[str] = None
        self._version_name: Optional[str] = None
        self._history_patches: dict[str, bool] = {}
        self._applied_patches: dict[str, bool] = {}
        self._encountered_patches: list[str] = []

    def run(self, generator: Generator[task.Task, Any, Any]):
        self._generator = generator
        # TODO: Do something with this task
        task = next(generator)  # this starts the generator
        # TODO: Check if the task is null?
        self._previous_task = task

    def resume(self):
        if self._generator is None:
            # This is never expected unless maybe there's an issue with the history
            raise TypeError(
                "The orchestrator generator is not initialized! Was the orchestration history corrupted?"
            )

        # We can resume the generator only if the previously yielded task
        # has reached a completed state. The only time this won't be the
        # case is if the user yielded on a WhenAll task and there are still
        # outstanding child tasks that need to be completed.
        while self._previous_task is not None and self._previous_task.is_complete:
            next_task = None
            if self._previous_task.is_failed:
                # Raise the failure as an exception to the generator.
                # The orchestrator can then either handle the exception or allow it to fail the orchestration.
                next_task = self._generator.throw(self._previous_task.get_exception())
            else:
                # Resume the generator with the previous result.
                # This will either return a Task or raise StopIteration if it's done.
                next_task = self._generator.send(self._previous_task.get_result())

            if not isinstance(next_task, task.Task):
                raise TypeError("The orchestrator generator yielded a non-Task object")
            self._previous_task = next_task

    def set_complete(
        self,
        result: Any,
        status: pb.OrchestrationStatus,
        is_result_encoded: bool = False,
    ):
        if self._is_complete:
            return

        self._is_complete = True
        self._completion_status = status
        self._pending_actions.clear()  # Cancel any pending actions

        self._result = result
        result_json: Optional[str] = None
        if result is not None:
            result_json = result if is_result_encoded else shared.to_json(result)
        action = ph.new_complete_orchestration_action(
            self.next_sequence_number(),
            status,
            result_json,
            router=pb.TaskRouter(sourceAppID=self._app_id) if self._app_id else None,
        )
        self._pending_actions[action.id] = action

    def set_failed(self, ex: Exception):
        if self._is_complete:
            return

        self._is_complete = True
        self._pending_actions.clear()  # Cancel any pending actions
        self._completion_status = pb.ORCHESTRATION_STATUS_FAILED

        action = ph.new_complete_orchestration_action(
            self.next_sequence_number(),
            pb.ORCHESTRATION_STATUS_FAILED,
            None,
            ph.new_failure_details(ex),
            router=pb.TaskRouter(sourceAppID=self._app_id) if self._app_id else None,
        )
        self._pending_actions[action.id] = action

    def set_version_not_registered(self):
        self._pending_actions.clear()
        self._completion_status = pb.ORCHESTRATION_STATUS_STALLED
        action = ph.new_orchestrator_version_not_available_action(self.next_sequence_number())
        self._pending_actions[action.id] = action

    def set_continued_as_new(self, new_input: Any, save_events: bool):
        if self._is_complete:
            return

        self._is_complete = True
        self._pending_actions.clear()  # Cancel any pending actions
        self._completion_status = pb.ORCHESTRATION_STATUS_CONTINUED_AS_NEW
        self._new_input = new_input
        self._save_events = save_events

    def get_actions(self) -> list[pb.OrchestratorAction]:
        if self._completion_status == pb.ORCHESTRATION_STATUS_CONTINUED_AS_NEW:
            # When continuing-as-new, we only return a single completion action.
            carryover_events: Optional[list[pb.HistoryEvent]] = None
            if self._save_events:
                carryover_events = []
                # We need to save the current set of pending events so that they can be
                # replayed when the new instance starts.
                for event_name, values in self._received_events.items():
                    for event_value in values:
                        encoded_value = shared.to_json(event_value) if event_value else None
                        carryover_events.append(
                            ph.new_event_raised_event(event_name, encoded_value)
                        )
            action = ph.new_complete_orchestration_action(
                self.next_sequence_number(),
                pb.ORCHESTRATION_STATUS_CONTINUED_AS_NEW,
                result=shared.to_json(self._new_input) if self._new_input is not None else None,
                failure_details=None,
                carryover_events=carryover_events,
                router=pb.TaskRouter(sourceAppID=self._app_id) if self._app_id else None,
            )
            return [action]
        else:
            return list(self._pending_actions.values())

    def next_sequence_number(self) -> int:
        self._sequence_number += 1
        return self._sequence_number

    @property
    def app_id(self) -> str:
        return self._app_id

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def current_utc_datetime(self) -> datetime:
        return self._current_utc_datetime

    @current_utc_datetime.setter
    def current_utc_datetime(self, value: datetime):
        self._current_utc_datetime = value

    @property
    def is_replaying(self) -> bool:
        return self._is_replaying

    def set_custom_status(self, custom_status: str) -> None:
        if custom_status is not None and not isinstance(custom_status, str):
            warnings.warn(
                "Passing a non-str value to set_custom_status is deprecated and will be "
                "removed in a future version. Serialize your value to a JSON string before calling.",
                DeprecationWarning,
                stacklevel=2,
            )
            self._encoded_custom_status = shared.to_json(custom_status)
        else:
            self._encoded_custom_status = custom_status

    def create_timer(self, fire_at: Union[datetime, timedelta]) -> task.Task:
        return self.create_timer_internal(fire_at)

    def create_timer_internal(
        self,
        fire_at: Union[datetime, timedelta],
        retryable_task: Optional[task.RetryableTask] = None,
    ) -> task.Task:
        id = self.next_sequence_number()
        if isinstance(fire_at, timedelta):
            fire_at = self.current_utc_datetime + fire_at
        action = ph.new_create_timer_action(id, fire_at)
        self._pending_actions[id] = action

        timer_task: task.TimerTask = task.TimerTask()
        if retryable_task is not None:
            timer_task.set_retryable_parent(retryable_task)
        self._pending_tasks[id] = timer_task
        return timer_task

    def call_activity(
        self,
        activity: Union[task.Activity[TInput, TOutput], str],
        *,
        input: Optional[TInput] = None,
        retry_policy: Optional[task.RetryPolicy] = None,
        app_id: Optional[str] = None,
    ) -> task.Task[TOutput]:
        id = self.next_sequence_number()
        task_execution_id = str(self.new_guid())

        self.call_activity_function_helper(
            id,
            activity,
            input=input,
            retry_policy=retry_policy,
            is_sub_orch=False,
            app_id=app_id,
            task_execution_id=task_execution_id,
        )
        return self._pending_tasks.get(id, task.CompletableTask())

    def call_sub_orchestrator(
        self,
        orchestrator: Union[task.Orchestrator[TInput, TOutput], str],
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
        retry_policy: Optional[task.RetryPolicy] = None,
        app_id: Optional[str] = None,
    ) -> task.Task[TOutput]:
        id = self.next_sequence_number()
        if isinstance(orchestrator, str):
            orchestrator_name = orchestrator
        else:
            orchestrator_name = task.get_name(orchestrator)
        self.call_activity_function_helper(
            id,
            orchestrator_name,
            input=input,
            retry_policy=retry_policy,
            is_sub_orch=True,
            instance_id=instance_id,
            app_id=app_id,
        )
        return self._pending_tasks.get(id, task.CompletableTask())

    def call_activity_function_helper(
        self,
        id: Optional[int],
        activity_function: Union[task.Activity[TInput, TOutput], str],
        *,
        input: Optional[TInput] = None,
        retry_policy: Optional[task.RetryPolicy] = None,
        is_sub_orch: bool = False,
        instance_id: Optional[str] = None,
        fn_task: Optional[task.CompletableTask[TOutput]] = None,
        app_id: Optional[str] = None,
        task_execution_id: str = "",
    ):
        if id is None:
            id = self.next_sequence_number()

        router = pb.TaskRouter()
        if self._app_id is not None:
            router.sourceAppID = self._app_id
        if app_id is not None:
            router.targetAppID = app_id

        if fn_task is None:
            encoded_input = shared.to_json(input) if input is not None else None
        else:
            # When retrying, input is already encoded as a string (or None).
            encoded_input = str(input) if input is not None else None
        if not is_sub_orch:
            name = (
                activity_function
                if isinstance(activity_function, str)
                else task.get_name(activity_function)
            )
            action = ph.new_schedule_task_action(
                id, name, encoded_input, router, task_execution_id=task_execution_id
            )
        else:
            if instance_id is None:
                # Create a deteministic instance ID based on the parent instance ID
                instance_id = f"{self.instance_id}:{id:04x}"
            if not isinstance(activity_function, str):
                raise ValueError("Orchestrator function name must be a string")
            action = ph.new_create_sub_orchestration_action(
                id, activity_function, instance_id, encoded_input, router
            )
        self._pending_actions[id] = action

        if fn_task is None:
            if retry_policy is None:
                fn_task = task.CompletableTask[TOutput]()
            else:
                fn_task = task.RetryableTask[TOutput](
                    retry_policy=retry_policy,
                    start_time=self.current_utc_datetime,
                    is_sub_orch=is_sub_orch,
                    task_name=name if not is_sub_orch else activity_function,
                    encoded_input=encoded_input,
                    task_execution_id=task_execution_id,
                    instance_id=instance_id,
                    app_id=app_id,
                )
        self._pending_tasks[id] = fn_task

    def wait_for_external_event(self, name: str) -> task.Task:
        # Check to see if this event has already been received, in which case we
        # can return it immediately. Otherwise, record out intent to receive an
        # event with the given name so that we can resume the generator when it
        # arrives. If there are multiple events with the same name, we return
        # them in the order they were received.
        external_event_task: task.CompletableTask = task.CompletableTask()
        event_name = name.casefold()
        event_list = self._received_events.get(event_name, None)
        if event_list:
            event_data = event_list.pop(0)
            if not event_list:
                del self._received_events[event_name]
            external_event_task.complete(event_data)
        else:
            task_list = self._pending_events.get(event_name, None)
            if not task_list:
                task_list = []
                self._pending_events[event_name] = task_list
            task_list.append(external_event_task)
        return external_event_task

    def continue_as_new(self, new_input, *, save_events: bool = False) -> None:
        if self._is_complete:
            return

        self.set_continued_as_new(new_input, save_events)

    def is_patched(self, patch_name: str) -> bool:
        is_patched = self._is_patched(patch_name)
        if is_patched:
            self._encountered_patches.append(patch_name)
        return is_patched

    def _is_patched(self, patch_name: str) -> bool:
        if patch_name in self._applied_patches:
            return self._applied_patches[patch_name]
        if patch_name in self._history_patches:
            self._applied_patches[patch_name] = True
            return True

        if self._is_replaying:
            self._applied_patches[patch_name] = False
            return False

        self._applied_patches[patch_name] = True
        return True


class ExecutionResults:
    actions: list[pb.OrchestratorAction]
    encoded_custom_status: Optional[str]
    version_name: Optional[str]
    patches: Optional[list[str]]

    def __init__(
        self,
        actions: list[pb.OrchestratorAction],
        encoded_custom_status: Optional[str],
        version_name: Optional[str] = None,
        patches: Optional[list[str]] = None,
    ):
        self.actions = actions
        self.encoded_custom_status = encoded_custom_status
        self.version_name = version_name
        self.patches = patches


class _OrchestrationExecutor:
    _generator: Optional[task.Orchestrator] = None

    def __init__(self, registry: _Registry, logger: logging.Logger):
        self._registry = registry
        self._logger = logger
        self._is_suspended = False
        self._suspended_events: list[pb.HistoryEvent] = []

    def execute(
        self,
        instance_id: str,
        old_events: Sequence[pb.HistoryEvent],
        new_events: Sequence[pb.HistoryEvent],
    ) -> ExecutionResults:
        if not new_events:
            raise task.OrchestrationStateError(
                "The new history event list must have at least one event in it."
            )

        ctx = _RuntimeOrchestrationContext(instance_id)
        try:
            # Rebuild local state by replaying old history into the orchestrator function
            self._logger.debug(
                f"{instance_id}: Rebuilding local state with {len(old_events)} history event..."
            )
            ctx._is_replaying = True
            for old_event in old_events:
                self.process_event(ctx, old_event)

            # Get new actions by executing newly received events into the orchestrator function
            if self._logger.level <= logging.DEBUG:
                summary = _get_new_event_summary(new_events)
                self._logger.debug(
                    f"{instance_id}: Processing {len(new_events)} new event(s): {summary}"
                )
            ctx._is_replaying = False
            for new_event in new_events:
                self.process_event(ctx, new_event)

        except VersionNotRegisteredException:
            ctx.set_version_not_registered()
        except Exception as ex:
            # Unhandled exceptions fail the orchestration
            ctx.set_failed(ex)

        if not ctx._is_complete:
            task_count = len(ctx._pending_tasks)
            event_count = len(ctx._pending_events)
            self._logger.info(
                f"{instance_id}: Orchestrator yielded with {task_count} task(s) and {event_count} event(s) outstanding."
            )
        elif (
            ctx._completion_status
            and ctx._completion_status is not pb.ORCHESTRATION_STATUS_CONTINUED_AS_NEW
        ):
            completion_status_str = ph.get_orchestration_status_str(ctx._completion_status)
            self._logger.info(
                f"{instance_id}: Orchestration completed with status: {completion_status_str}"
            )

        actions = ctx.get_actions()
        if self._logger.level <= logging.DEBUG:
            self._logger.debug(
                f"{instance_id}: Returning {len(actions)} action(s): {_get_action_summary(actions)}"
            )
        return ExecutionResults(
            actions=actions,
            encoded_custom_status=ctx._encoded_custom_status,
            version_name=getattr(ctx, "_version_name", None),
            patches=ctx._encountered_patches,
        )

    def process_event(self, ctx: _RuntimeOrchestrationContext, event: pb.HistoryEvent) -> None:
        if self._is_suspended and _is_suspendable(event):
            # We are suspended, so we need to buffer this event until we are resumed
            self._suspended_events.append(event)
            return

        # CONSIDER: change to a switch statement with event.WhichOneof("eventType")
        try:
            if event.HasField("orchestratorStarted"):
                ctx.current_utc_datetime = event.timestamp.ToDatetime()
                if event.orchestratorStarted.version:
                    if event.orchestratorStarted.version.name:
                        ctx._orchestrator_version_name = event.orchestratorStarted.version.name
                    for patch in event.orchestratorStarted.version.patches:
                        ctx._history_patches[patch] = True
            elif event.HasField("executionStarted"):
                if event.router.targetAppID:
                    ctx._app_id = event.router.targetAppID
                else:
                    ctx._app_id = event.router.sourceAppID

                version_name = None
                if ctx._orchestrator_version_name:
                    version_name = ctx._orchestrator_version_name

                # TODO: Check if we already started the orchestration
                fn, version_used = self._registry.get_orchestrator(
                    event.executionStarted.name, version_name=version_name
                )

                if fn is None:
                    raise OrchestratorNotRegisteredError(
                        f"A '{event.executionStarted.name}' orchestrator was not registered."
                    )

                if version_used is not None:
                    ctx._version_name = version_used

                # deserialize the input, if any
                input = None
                if (
                    event.executionStarted.input is not None
                    and event.executionStarted.input.value != ""
                ):
                    input = shared.from_json(event.executionStarted.input.value)

                result = fn(ctx, input)  # this does not execute the generator, only creates it
                if isinstance(result, GeneratorType):
                    # Start the orchestrator's generator function
                    ctx.run(result)
                else:
                    # This is an orchestrator that doesn't schedule any tasks
                    ctx.set_complete(result, pb.ORCHESTRATION_STATUS_COMPLETED)
            elif event.HasField("timerCreated"):
                # This history event confirms that the timer was successfully scheduled.
                # Remove the timerCreated event from the pending action list so we don't schedule it again.
                timer_id = event.eventId
                action = ctx._pending_actions.pop(timer_id, None)
                if not action:
                    raise _get_non_determinism_error(timer_id, task.get_name(ctx.create_timer))
                elif not action.HasField("createTimer"):
                    expected_method_name = task.get_name(ctx.create_timer)
                    raise _get_wrong_action_type_error(timer_id, expected_method_name, action)
            elif event.HasField("timerFired"):
                timer_id = event.timerFired.timerId
                timer_task = ctx._pending_tasks.pop(timer_id, None)
                if not timer_task:
                    # TODO: Should this be an error? When would it ever happen?
                    if not ctx._is_replaying:
                        self._logger.warning(
                            f"{ctx.instance_id}: Ignoring unexpected timerFired event with ID = {timer_id}."
                        )
                    return
                timer_task.complete(None)
                if timer_task._retryable_parent is not None:
                    retryable = timer_task._retryable_parent

                    ctx.call_activity_function_helper(
                        id=None,  # Get a new sequence number
                        activity_function=retryable._task_name,
                        input=retryable._encoded_input,
                        retry_policy=retryable._retry_policy,
                        is_sub_orch=retryable._is_sub_orch,
                        instance_id=retryable._instance_id,
                        fn_task=retryable,
                        app_id=retryable._app_id,
                        task_execution_id=retryable._task_execution_id,
                    )
                else:
                    ctx.resume()
            elif event.HasField("taskScheduled"):
                # This history event confirms that the activity execution was successfully scheduled.
                # Remove the taskScheduled event from the pending action list so we don't schedule it again.
                task_id = event.eventId
                action = ctx._pending_actions.pop(task_id, None)
                activity_task = ctx._pending_tasks.get(task_id, None)
                if not action:
                    raise _get_non_determinism_error(task_id, task.get_name(ctx.call_activity))
                elif not action.HasField("scheduleTask"):
                    expected_method_name = task.get_name(ctx.call_activity)
                    raise _get_wrong_action_type_error(task_id, expected_method_name, action)
                elif action.scheduleTask.name != event.taskScheduled.name:
                    raise _get_wrong_action_name_error(
                        task_id,
                        method_name=task.get_name(ctx.call_activity),
                        expected_task_name=event.taskScheduled.name,
                        actual_task_name=action.scheduleTask.name,
                    )
            elif event.HasField("taskCompleted"):
                # This history event contains the result of a completed activity task.
                task_id = event.taskCompleted.taskScheduledId
                activity_task = ctx._pending_tasks.pop(task_id, None)
                if not activity_task:
                    # TODO: Should this be an error? When would it ever happen?
                    if not ctx.is_replaying:
                        self._logger.warning(
                            f"{ctx.instance_id}: Ignoring unexpected taskCompleted event with ID = {task_id}."
                        )
                    return
                result = None
                if not ph.is_empty(event.taskCompleted.result):
                    result = shared.from_json(event.taskCompleted.result.value)
                activity_task.complete(result)
                ctx.resume()
            elif event.HasField("taskFailed"):
                task_id = event.taskFailed.taskScheduledId
                activity_task = ctx._pending_tasks.pop(task_id, None)
                if not activity_task:
                    # TODO: Should this be an error? When would it ever happen?
                    if not ctx.is_replaying:
                        self._logger.warning(
                            f"{ctx.instance_id}: Ignoring unexpected taskFailed event with ID = {task_id}."
                        )
                    return

                if isinstance(activity_task, task.RetryableTask):
                    if activity_task._retry_policy is not None:
                        # Check for non-retryable errors by type name
                        if task.is_error_non_retryable(
                            event.taskFailed.failureDetails.errorType, activity_task._retry_policy
                        ):
                            activity_task.fail(
                                f"{ctx.instance_id}: Activity task #{task_id} failed: {event.taskFailed.failureDetails.errorMessage}",
                                event.taskFailed.failureDetails,
                            )
                            ctx.resume()
                        else:
                            next_delay = activity_task.compute_next_delay()
                            if next_delay is None:
                                activity_task.fail(
                                    f"{ctx.instance_id}: Activity task #{task_id} failed: {event.taskFailed.failureDetails.errorMessage}",
                                    event.taskFailed.failureDetails,
                                )
                                ctx.resume()
                            else:
                                activity_task.increment_attempt_count()
                                ctx.create_timer_internal(next_delay, activity_task)
                elif isinstance(activity_task, task.CompletableTask):
                    activity_task.fail(
                        f"{ctx.instance_id}: Activity task #{task_id} failed: {event.taskFailed.failureDetails.errorMessage}",
                        event.taskFailed.failureDetails,
                    )
                    ctx.resume()
                else:
                    raise TypeError("Unexpected task type")
            elif event.HasField("subOrchestrationInstanceCreated"):
                # This history event confirms that the sub-orchestration execution was successfully scheduled.
                # Remove the subOrchestrationInstanceCreated event from the pending action list so we don't schedule it again.
                task_id = event.eventId
                action = ctx._pending_actions.pop(task_id, None)
                if not action:
                    raise _get_non_determinism_error(
                        task_id, task.get_name(ctx.call_sub_orchestrator)
                    )
                elif not action.HasField("createSubOrchestration"):
                    expected_method_name = task.get_name(ctx.call_sub_orchestrator)
                    raise _get_wrong_action_type_error(task_id, expected_method_name, action)
                elif (
                    action.createSubOrchestration.name != event.subOrchestrationInstanceCreated.name
                ):
                    raise _get_wrong_action_name_error(
                        task_id,
                        method_name=task.get_name(ctx.call_sub_orchestrator),
                        expected_task_name=event.subOrchestrationInstanceCreated.name,
                        actual_task_name=action.createSubOrchestration.name,
                    )
            elif event.HasField("subOrchestrationInstanceCompleted"):
                task_id = event.subOrchestrationInstanceCompleted.taskScheduledId
                sub_orch_task = ctx._pending_tasks.pop(task_id, None)
                if not sub_orch_task:
                    # TODO: Should this be an error? When would it ever happen?
                    if not ctx.is_replaying:
                        self._logger.warning(
                            f"{ctx.instance_id}: Ignoring unexpected subOrchestrationInstanceCompleted event with ID = {task_id}."
                        )
                    return
                result = None
                if not ph.is_empty(event.subOrchestrationInstanceCompleted.result):
                    result = shared.from_json(event.subOrchestrationInstanceCompleted.result.value)
                sub_orch_task.complete(result)
                ctx.resume()
            elif event.HasField("subOrchestrationInstanceFailed"):
                failedEvent = event.subOrchestrationInstanceFailed
                task_id = failedEvent.taskScheduledId
                sub_orch_task = ctx._pending_tasks.pop(task_id, None)
                if not sub_orch_task:
                    # TODO: Should this be an error? When would it ever happen?
                    if not ctx.is_replaying:
                        self._logger.warning(
                            f"{ctx.instance_id}: Ignoring unexpected subOrchestrationInstanceFailed event with ID = {task_id}."
                        )
                    return
                if isinstance(sub_orch_task, task.RetryableTask):
                    if sub_orch_task._retry_policy is not None:
                        # Check for non-retryable errors by type name
                        if task.is_error_non_retryable(
                            failedEvent.failureDetails.errorType, sub_orch_task._retry_policy
                        ):
                            sub_orch_task.fail(
                                f"Sub-orchestration task #{task_id} failed: {failedEvent.failureDetails.errorMessage}",
                                failedEvent.failureDetails,
                            )
                            ctx.resume()
                        else:
                            next_delay = sub_orch_task.compute_next_delay()
                            if next_delay is None:
                                sub_orch_task.fail(
                                    f"Sub-orchestration task #{task_id} failed: {failedEvent.failureDetails.errorMessage}",
                                    failedEvent.failureDetails,
                                )
                                ctx.resume()
                            else:
                                sub_orch_task.increment_attempt_count()
                                ctx.create_timer_internal(next_delay, sub_orch_task)
                elif isinstance(sub_orch_task, task.CompletableTask):
                    sub_orch_task.fail(
                        f"Sub-orchestration task #{task_id} failed: {failedEvent.failureDetails.errorMessage}",
                        failedEvent.failureDetails,
                    )
                    ctx.resume()
                else:
                    raise TypeError("Unexpected sub-orchestration task type")
            elif event.HasField("eventRaised"):
                # event names are case-insensitive
                event_name = event.eventRaised.name.casefold()
                if not ctx.is_replaying:
                    self._logger.info(f"{ctx.instance_id} Event raised: {event_name}")
                task_list = ctx._pending_events.get(event_name, None)
                decoded_result: Optional[Any] = None
                if task_list:
                    event_task = task_list.pop(0)
                    if not ph.is_empty(event.eventRaised.input):
                        decoded_result = shared.from_json(event.eventRaised.input.value)
                    event_task.complete(decoded_result)
                    if not task_list:
                        del ctx._pending_events[event_name]
                    ctx.resume()
                else:
                    # buffer the event
                    event_list = ctx._received_events.get(event_name, None)
                    if not event_list:
                        event_list = []
                        ctx._received_events[event_name] = event_list
                    if not ph.is_empty(event.eventRaised.input):
                        decoded_result = shared.from_json(event.eventRaised.input.value)
                    event_list.append(decoded_result)
                    if not ctx.is_replaying:
                        self._logger.info(
                            f"{ctx.instance_id}: Event '{event_name}' has been buffered as there are no tasks waiting for it."
                        )
            elif event.HasField("executionSuspended"):
                if not self._is_suspended and not ctx.is_replaying:
                    self._logger.info(f"{ctx.instance_id}: Execution suspended.")
                self._is_suspended = True
            elif event.HasField("executionResumed") and self._is_suspended:
                if not ctx.is_replaying:
                    self._logger.info(f"{ctx.instance_id}: Resuming execution.")
                self._is_suspended = False
                for e in self._suspended_events:
                    self.process_event(ctx, e)
                self._suspended_events = []
            elif event.HasField("executionTerminated"):
                if not ctx.is_replaying:
                    self._logger.info(f"{ctx.instance_id}: Execution terminating.")
                encoded_output = (
                    event.executionTerminated.input.value
                    if not ph.is_empty(event.executionTerminated.input)
                    else None
                )
                ctx.set_complete(
                    encoded_output,
                    pb.ORCHESTRATION_STATUS_TERMINATED,
                    is_result_encoded=True,
                )
            elif event.HasField("executionStalled"):
                # Nothing to do
                pass
            else:
                eventType = event.WhichOneof("eventType")
                raise task.OrchestrationStateError(
                    f"Don't know how to handle event of type '{eventType}'"
                )
        except StopIteration as generatorStopped:
            # The orchestrator generator function completed
            ctx.set_complete(generatorStopped.value, pb.ORCHESTRATION_STATUS_COMPLETED)


class _ActivityExecutor:
    def __init__(self, registry: _Registry, logger: logging.Logger):
        self._registry = registry
        self._logger = logger

    def execute(
        self,
        orchestration_id: str,
        name: str,
        task_id: int,
        encoded_input: Optional[str],
        task_execution_id: str = "",
    ) -> Optional[str]:
        """Executes an activity function and returns the serialized result, if any."""
        self._logger.debug(f"{orchestration_id}/{task_id}: Executing activity '{name}'...")
        fn = self._registry.get_activity(name)
        if not fn:
            raise ActivityNotRegisteredError(
                f"Activity function named '{name}' was not registered!"
            )

        activity_input = shared.from_json(encoded_input) if encoded_input else None
        ctx = task.ActivityContext(orchestration_id, task_id, task_execution_id)

        # Execute the activity function
        activity_output = fn(ctx, activity_input)

        encoded_output = shared.to_json(activity_output) if activity_output is not None else None
        chars = len(encoded_output) if encoded_output else 0
        self._logger.debug(
            f"{orchestration_id}/{task_id}: Activity '{name}' completed successfully with {chars} char(s) of encoded output."
        )
        return encoded_output


def _get_non_determinism_error(task_id: int, action_name: str) -> task.NonDeterminismError:
    return task.NonDeterminismError(
        f"A previous execution called {action_name} with ID={task_id}, but the current "
        f"execution doesn't have this action with this ID. This problem occurs when either "
        f"the orchestration has non-deterministic logic or if the code was changed after an "
        f"instance of this orchestration already started running."
    )


def _get_wrong_action_type_error(
    task_id: int, expected_method_name: str, action: pb.OrchestratorAction
) -> task.NonDeterminismError:
    unexpected_method_name = _get_method_name_for_action(action)
    return task.NonDeterminismError(
        f"Failed to restore orchestration state due to a history mismatch: A previous execution called "
        f"{expected_method_name} with ID={task_id}, but the current execution is instead trying to call "
        f"{unexpected_method_name} as part of rebuilding it's history. This kind of mismatch can happen if an "
        f"orchestration has non-deterministic logic or if the code was changed after an instance of this "
        f"orchestration already started running."
    )


def _get_wrong_action_name_error(
    task_id: int, method_name: str, expected_task_name: str, actual_task_name: str
) -> task.NonDeterminismError:
    return task.NonDeterminismError(
        f"Failed to restore orchestration state due to a history mismatch: A previous execution called "
        f"{method_name} with name='{expected_task_name}' and sequence number {task_id}, but the current "
        f"execution is instead trying to call {actual_task_name} as part of rebuilding it's history. "
        f"This kind of mismatch can happen if an orchestration has non-deterministic logic or if the code "
        f"was changed after an instance of this orchestration already started running."
    )


def _get_method_name_for_action(action: pb.OrchestratorAction) -> str:
    action_type = action.WhichOneof("orchestratorActionType")
    if action_type == "scheduleTask":
        return task.get_name(task.OrchestrationContext.call_activity)
    elif action_type == "createTimer":
        return task.get_name(task.OrchestrationContext.create_timer)
    elif action_type == "createSubOrchestration":
        return task.get_name(task.OrchestrationContext.call_sub_orchestrator)
    # elif action_type == "sendEvent":
    #    return task.get_name(task.OrchestrationContext.send_event)
    else:
        raise NotImplementedError(f"Action type '{action_type}' not supported!")


def _get_new_event_summary(new_events: Sequence[pb.HistoryEvent]) -> str:
    """Returns a summary of the new events that can be used for logging."""
    if not new_events:
        return "[]"
    elif len(new_events) == 1:
        return f"[{new_events[0].WhichOneof('eventType')}]"
    else:
        counts: dict[str, int] = {}
        for event in new_events:
            event_type = event.WhichOneof("eventType")
            counts[event_type] = counts.get(event_type, 0) + 1
        return f"[{', '.join(f'{name}={count}' for name, count in counts.items())}]"


def _get_action_summary(new_actions: Sequence[pb.OrchestratorAction]) -> str:
    """Returns a summary of the new actions that can be used for logging."""
    if not new_actions:
        return "[]"
    elif len(new_actions) == 1:
        return f"[{new_actions[0].WhichOneof('orchestratorActionType')}]"
    else:
        counts: dict[str, int] = {}
        for action in new_actions:
            action_type = action.WhichOneof("orchestratorActionType")
            counts[action_type] = counts.get(action_type, 0) + 1
        return f"[{', '.join(f'{name}={count}' for name, count in counts.items())}]"


def _is_suspendable(event: pb.HistoryEvent) -> bool:
    """Returns true if the event is one that can be suspended and resumed."""
    return event.WhichOneof("eventType") not in [
        "executionResumed",
        "executionTerminated",
    ]


class _AsyncWorkerManager:
    def __init__(self, concurrency_options: ConcurrencyOptions, logger: logging.Logger):
        self.concurrency_options = concurrency_options
        self.activity_semaphore = None
        self.orchestration_semaphore = None
        # Don't create queues here - defer until we have an event loop
        self.activity_queue: Optional[asyncio.Queue] = None
        self.orchestration_queue: Optional[asyncio.Queue] = None
        self._queue_event_loop: Optional[asyncio.AbstractEventLoop] = None
        # Store work items when no event loop is available
        self._pending_activity_work: list = []
        self._pending_orchestration_work: list = []
        self.thread_pool = ThreadPoolExecutor(
            max_workers=concurrency_options.maximum_thread_pool_workers,
            thread_name_prefix="DurableTask",
        )
        self._shutdown = False
        self._logger = logger

    def _ensure_queues_for_current_loop(self):
        """Ensure queues are bound to the current event loop."""
        try:
            current_loop = asyncio.get_running_loop()
            if current_loop.is_closed():
                return
        except RuntimeError as e:
            self._logger.exception(f"Failed to get event loop {e}")
            # No event loop running, can't create queues
            return

        # Check if queues are already properly set up for current loop
        if self._queue_event_loop is current_loop:
            if self.activity_queue is not None and self.orchestration_queue is not None:
                # Queues are already bound to the current loop and exist
                return

        # Need to recreate queues for the current event loop
        # First, preserve any existing work items
        existing_activity_items = []
        existing_orchestration_items = []

        if self.activity_queue is not None:
            try:
                while not self.activity_queue.empty():
                    existing_activity_items.append(self.activity_queue.get_nowait())
            except Exception as e:
                self._logger.debug(f"Failed to append to the activity queue {e}")
                pass

        if self.orchestration_queue is not None:
            try:
                while not self.orchestration_queue.empty():
                    existing_orchestration_items.append(self.orchestration_queue.get_nowait())
            except Exception as e:
                self._logger.debug(f"Failed to append to the orchestration queue {e}")
                pass

        # Create fresh queues for the current event loop
        self.activity_queue = asyncio.Queue()
        self.orchestration_queue = asyncio.Queue()
        self._queue_event_loop = current_loop

        # Restore the work items to the new queues
        for item in existing_activity_items:
            self.activity_queue.put_nowait(item)
        for item in existing_orchestration_items:
            self.orchestration_queue.put_nowait(item)

        # Move pending work items to the queues
        for item in self._pending_activity_work:
            self.activity_queue.put_nowait(item)
        for item in self._pending_orchestration_work:
            self.orchestration_queue.put_nowait(item)

        # Clear the pending work lists
        self._pending_activity_work.clear()
        self._pending_orchestration_work.clear()

    async def run(self):
        # Reset shutdown flag in case this manager is being reused
        self._shutdown = False

        # Ensure queues are properly bound to the current event loop
        self._ensure_queues_for_current_loop()

        # Create semaphores in the current event loop
        self.activity_semaphore = asyncio.Semaphore(
            self.concurrency_options.maximum_concurrent_activity_work_items
        )
        self.orchestration_semaphore = asyncio.Semaphore(
            self.concurrency_options.maximum_concurrent_orchestration_work_items
        )

        # Start background consumers for each work type
        if self.activity_queue is not None and self.orchestration_queue is not None:
            await asyncio.gather(
                self._consume_queue(self.activity_queue, self.activity_semaphore),
                self._consume_queue(self.orchestration_queue, self.orchestration_semaphore),
            )

    async def _consume_queue(self, queue: asyncio.Queue, semaphore: asyncio.Semaphore):
        # List to track running tasks
        running_tasks: set[asyncio.Task] = set()

        try:
            while True:
                # Clean up completed tasks
                done_tasks = {task for task in running_tasks if task.done()}
                running_tasks -= done_tasks

                # Exit if shutdown is set and the queue is empty and no tasks are running
                if self._shutdown and queue.empty() and not running_tasks:
                    break

                try:
                    work = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Check for cancellation during timeout and exit while loop if shutting down
                    if self._shutdown:
                        break
                    continue  # otherwise wait for work item to become available and loop again
                except asyncio.CancelledError:
                    # Propagate cancellation
                    raise

                func, args, kwargs = work
                # Create a concurrent task for processing
                task = asyncio.create_task(
                    self._process_work_item(semaphore, queue, func, args, kwargs)
                )
                running_tasks.add(task)
        # handle the cancellation bubbled up from the loop
        except asyncio.CancelledError:
            # Cancel any remaining running tasks
            for task in running_tasks:
                if not task.done():
                    task.cancel()
            # Wait briefly for tasks to cancel, but don't block indefinitely
            if running_tasks:
                await asyncio.gather(*running_tasks, return_exceptions=True)
            raise

    async def _process_work_item(
        self, semaphore: asyncio.Semaphore, queue: asyncio.Queue, func, args, kwargs
    ):
        async with semaphore:
            try:
                await self._run_func(func, *args, **kwargs)
            finally:
                queue.task_done()

    async def _run_func(self, func, *args, **kwargs):
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()
            # Avoid submitting to executor after shutdown
            if (
                getattr(self, "_shutdown", False)
                and getattr(self, "thread_pool", None)
                and getattr(self.thread_pool, "_shutdown", False)
            ):
                return None
            result = await loop.run_in_executor(self.thread_pool, lambda: func(*args, **kwargs))
            return result

    def submit_activity(self, func, *args, **kwargs):
        work_item = (func, args, kwargs)
        self._ensure_queues_for_current_loop()
        if self.activity_queue is not None:
            self.activity_queue.put_nowait(work_item)
        else:
            # No event loop running, store in pending list
            self._pending_activity_work.append(work_item)

    def submit_orchestration(self, func, *args, **kwargs):
        work_item = (func, args, kwargs)
        self._ensure_queues_for_current_loop()
        if self.orchestration_queue is not None:
            self.orchestration_queue.put_nowait(work_item)
        else:
            # No event loop running, store in pending list
            self._pending_orchestration_work.append(work_item)

    def shutdown(self):
        self._shutdown = True
        # Shutdown thread pool. Since we've already cancelled worker_task and set _shutdown=True,
        # no new work should be submitted and existing work should complete quickly.
        # ThreadPoolExecutor.shutdown(wait=True) doesn't support a timeout, but with proper
        # cancellation in place, threads should exit promptly, otherwise this will hang and block shutdown for the application.
        self.thread_pool.shutdown(wait=True)

    def reset_for_new_run(self):
        """Reset the manager state for a new run."""
        self._shutdown = False
        # Clear any existing queues - they'll be recreated when needed
        if self.activity_queue is not None:
            # Clear existing queue by creating a new one
            # This ensures no items from previous runs remain
            try:
                while not self.activity_queue.empty():
                    self.activity_queue.get_nowait()
            except Exception:
                pass
        if self.orchestration_queue is not None:
            try:
                while not self.orchestration_queue.empty():
                    self.orchestration_queue.get_nowait()
            except Exception:
                pass
        # Clear pending work lists
        self._pending_activity_work.clear()
        self._pending_orchestration_work.clear()


# Export public API
__all__ = ["ConcurrencyOptions", "TaskHubGrpcWorker"]
