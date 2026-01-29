# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import inspect
import time
from functools import wraps
from typing import Optional, Sequence, TypeVar, Union

import grpc
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.logger import Logger, LoggerOptions
from dapr.ext.workflow.util import getAddress
from dapr.ext.workflow.workflow_activity_context import Activity, WorkflowActivityContext
from dapr.ext.workflow.workflow_context import Workflow
from durabletask import task, worker

from dapr.clients import DaprInternalError
from dapr.clients.http.client import DAPR_API_TOKEN_HEADER
from dapr.conf import settings
from dapr.conf.helpers import GrpcEndpoint

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')

ClientInterceptor = Union[
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
]


class WorkflowRuntime:
    """WorkflowRuntime is the entry point for registering workflows and activities."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[str] = None,
        logger_options: Optional[LoggerOptions] = None,
        interceptors: Optional[Sequence[ClientInterceptor]] = None,
        maximum_concurrent_activity_work_items: Optional[int] = None,
        maximum_concurrent_orchestration_work_items: Optional[int] = None,
        maximum_thread_pool_workers: Optional[int] = None,
    ):
        self._logger = Logger('WorkflowRuntime', logger_options)
        
        metadata = tuple()
        if settings.DAPR_API_TOKEN:
            metadata = ((DAPR_API_TOKEN_HEADER, settings.DAPR_API_TOKEN),)
        address = getAddress(host, port)

        try:
            uri = GrpcEndpoint(address)
        except ValueError as error:
            raise DaprInternalError(f'{error}') from error

        options = self._logger.get_options()
        self.__worker = worker.TaskHubGrpcWorker(
            host_address=uri.endpoint,
            metadata=metadata,
            secure_channel=uri.tls,
            log_handler=options.log_handler,
            log_formatter=options.log_formatter,
            interceptors=interceptors,
            concurrency_options=worker.ConcurrencyOptions(
                maximum_concurrent_activity_work_items=maximum_concurrent_activity_work_items,
                maximum_concurrent_orchestration_work_items=maximum_concurrent_orchestration_work_items,
                maximum_thread_pool_workers=maximum_thread_pool_workers,
            ),
        )

    def register_workflow(self, fn: Workflow, *, name: Optional[str] = None):
        self._logger.info(f"Registering workflow '{fn.__name__}' with runtime")

        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: Optional[TInput] = None):
            """Responsible to call Workflow function in orchestrationWrapper"""
            instance_id = getattr(ctx, 'instance_id', 'unknown')
            
            try:
                daprWfContext = DaprWorkflowContext(ctx, self._logger.get_options())
                if inp is None:
                    result = fn(daprWfContext)
                else:
                    result = fn(daprWfContext, inp)
                return result
            except Exception as e:
                self._logger.exception(f"Workflow execution failed - "
                                 f"instance_id: {instance_id}, error: {e}")
                raise

        if hasattr(fn, '_workflow_registered'):
            # whenever a workflow is registered, it has a _dapr_alternate_name attribute
            alt_name = fn.__dict__['_dapr_alternate_name']
            raise ValueError(f'Workflow {fn.__name__} already registered as {alt_name}')
        if hasattr(fn, '_dapr_alternate_name'):
            alt_name = fn._dapr_alternate_name
            if name is not None:
                m = f'Workflow {fn.__name__} already has an alternate name {alt_name}'
                raise ValueError(m)
        else:
            fn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__

        self.__worker._registry.add_named_orchestrator(
            fn.__dict__['_dapr_alternate_name'], orchestrationWrapper
        )
        fn.__dict__['_workflow_registered'] = True

    def register_activity(self, fn: Activity, *, name: Optional[str] = None):
        """Registers a workflow activity as a function that takes
        a specified input type and returns a specified output type.
        """
        self._logger.info(f"Registering activity '{fn.__name__}' with runtime")

        def activityWrapper(ctx: task.ActivityContext, inp: Optional[TInput] = None):
            """Responsible to call Activity function in activityWrapper"""
            activity_id = getattr(ctx, 'task_id', 'unknown')
            
            try:
                wfActivityContext = WorkflowActivityContext(ctx)
                if inp is None:
                    result = fn(wfActivityContext)
                else:
                    result = fn(wfActivityContext, inp)
                return result
            except Exception as e:
                self._logger.exception(f"Activity execution failed - "
                                 f"task_id: {activity_id}, error: {e}")
                raise

        if hasattr(fn, '_activity_registered'):
            # whenever an activity is registered, it has a _dapr_alternate_name attribute
            alt_name = fn.__dict__['_dapr_alternate_name']
            raise ValueError(f'Activity {fn.__name__} already registered as {alt_name}')
        if hasattr(fn, '_dapr_alternate_name'):
            alt_name = fn._dapr_alternate_name
            if name is not None:
                m = f'Activity {fn.__name__} already has an alternate name {alt_name}'
                raise ValueError(m)
        else:
            fn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__

        self.__worker._registry.add_named_activity(
            fn.__dict__['_dapr_alternate_name'], activityWrapper
        )
        fn.__dict__['_activity_registered'] = True

    def wait_for_worker_ready(self, timeout: float = 30.0) -> bool:
        """
        Wait for the worker's gRPC stream to become ready to receive work items.
        
        This method polls the worker's is_worker_ready() method until it returns True
        or the timeout is reached.

        Args:
            timeout: Maximum time in seconds to wait for the worker to be ready.
                    Defaults to 30 seconds.

        Returns:
            True if the worker's gRPC stream is ready to receive work items, False if timeout.
        """
        if not hasattr(self.__worker, 'is_worker_ready'):
            return False
        
        elapsed = 0.0
        poll_interval = 0.1  # 100ms
        
        while elapsed < timeout:
            if self.__worker.is_worker_ready():
                return True
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        self._logger.warning(
            f"WorkflowRuntime worker readiness check timed out after {timeout} seconds"
        )
        return False

    def start(self):
        """Starts the listening for work items on a background thread.
        
        This method waits for the worker's gRPC stream to be fully initialized
        before returning, ensuring that workflows can be scheduled immediately
        after start() completes.
        """
        try:
            try:
                self.__worker.start()
            except Exception as start_error:
                self._logger.exception(
                    f"WorkflowRuntime worker did not start: {start_error}"
                )
                raise
            
            # Verify the worker and its stream reader are ready
            if hasattr(self.__worker, 'is_worker_ready'):
                try:
                    is_ready = self.wait_for_worker_ready(timeout=5.0)
                    if not is_ready:
                        raise RuntimeError("WorkflowRuntime worker and its stream are not ready")
                    else:
                        self._logger.debug("WorkflowRuntime worker is ready and its stream can receive work items")
                except Exception as ready_error:
                    self._logger.exception(
                        f"WorkflowRuntime wait_for_worker_ready() raised exception: {ready_error}"
                    )
                    raise ready_error
            else:
                self._logger.warning(
                    "Unable to verify stream readiness. Workflows scheduled immediately may not be received."
                )
        except Exception:
            raise
    

    def shutdown(self):
        """Stops the listening for work items on a background thread."""
        try:
            self.__worker.stop()
        except Exception:
            raise

    def workflow(self, __fn: Workflow = None, *, name: Optional[str] = None):
        """Decorator to register a workflow function.

        This example shows how to register a workflow function with a name:

                from dapr.ext.workflow import WorkflowRuntime
                wfr = WorkflowRuntime()

                @wfr.workflow(name="add")
                def add(ctx, x: int, y: int) -> int:
                    return x + y

        This example shows how to register a workflow function without
        an alternate name:

                    from dapr.ext.workflow import WorkflowRuntime
                    wfr = WorkflowRuntime()

                    @wfr.workflow
                    def add(ctx, x: int, y: int) -> int:
                        return x + y

        Args:
            name (Optional[str], optional): Name to identify the workflow function as in
            the workflow runtime. Defaults to None.
        """

        def wrapper(fn: Workflow):
            self.register_workflow(fn, name=name)

            @wraps(fn)
            def innerfn():
                return fn

            if hasattr(fn, '_dapr_alternate_name'):
                innerfn.__dict__['_dapr_alternate_name'] = fn.__dict__['_dapr_alternate_name']
            else:
                innerfn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__
            innerfn.__signature__ = inspect.signature(fn)
            return innerfn

        if __fn:
            # This case is true when the decorator is used without arguments
            # and the function to be decorated is passed as the first argument.
            return wrapper(__fn)

        return wrapper

    def activity(self, __fn: Activity = None, *, name: Optional[str] = None):
        """Decorator to register an activity function.

        This example shows how to register an activity function with an alternate name:

            from dapr.ext.workflow import WorkflowRuntime
            wfr = WorkflowRuntime()

            @wfr.activity(name="add")
            def add(ctx, x: int, y: int) -> int:
                return x + y

        This example shows how to register an activity function without an alternate name:

                from dapr.ext.workflow import WorkflowRuntime
                wfr = WorkflowRuntime()

                @wfr.activity
                def add(ctx, x: int, y: int) -> int:
                    return x + y

        Args:
            name (Optional[str], optional): Name to identify the activity function as in
            the workflow runtime. Defaults to None.
        """

        def wrapper(fn: Activity):
            self.register_activity(fn, name=name)

            @wraps(fn)
            def innerfn():
                return fn

            if hasattr(fn, '_dapr_alternate_name'):
                innerfn.__dict__['_dapr_alternate_name'] = fn.__dict__['_dapr_alternate_name']
            else:
                innerfn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__
            innerfn.__signature__ = inspect.signature(fn)
            return innerfn

        if __fn:
            # This case is true when the decorator is used without arguments
            # and the function to be decorated is passed as the first argument.
            return wrapper(__fn)

        return wrapper


def alternate_name(name: Optional[str] = None):
    """Decorator to register a workflow or activity function with an alternate name.

    This example shows how to register a workflow function with an alternate name:

            from dapr.ext.workflow import WorkflowRuntime
            wfr = WorkflowRuntime()

            @wfr.workflow
            @alternate_name(add")
            def add(ctx, x: int, y: int) -> int:
                return x + y

    Args:
        name (Optional[str], optional): Name to identify the workflow or activity function as in
        the workflow runtime. Defaults to None.
    """

    def wrapper(fn: any):
        if hasattr(fn, '_dapr_alternate_name'):
            raise ValueError(
                f'Function {fn.__name__} already has an alternate name {fn._dapr_alternate_name}'
            )
        fn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__

        @wraps(fn)
        def innerfn(*args, **kwargs):
            return fn(*args, **kwargs)

        innerfn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__
        innerfn.__signature__ = inspect.signature(fn)
        return innerfn

    return wrapper
