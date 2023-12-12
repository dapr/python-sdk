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
from functools import wraps
from typing import Optional, TypeVar

from durabletask import worker, task

from dapr.ext.workflow.workflow_context import Workflow
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import Activity, WorkflowActivityContext
from dapr.ext.workflow.util import getAddress

from dapr.clients import DaprInternalError
from dapr.clients.http.client import DAPR_API_TOKEN_HEADER
from dapr.conf import settings
from dapr.conf.helpers import GrpcEndpoint

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowRuntime:
    """WorkflowRuntime is the entry point for registering workflows and activities.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[str] = None):
        metadata = tuple()
        if settings.DAPR_API_TOKEN:
            metadata = ((DAPR_API_TOKEN_HEADER, settings.DAPR_API_TOKEN),)
        address = getAddress(host, port)

        try:
            uri = GrpcEndpoint(address)
        except ValueError as error:
            raise DaprInternalError(f'{error}') from error

        self.__worker = worker.TaskHubGrpcWorker(host_address=uri.endpoint, metadata=metadata,
                                                 secure_channel=uri.tls)

    def register_workflow(self, fn: Workflow, *, name: Optional[str] = None):
        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: Optional[TInput] = None):
            """Responsible to call Workflow function in orchestrationWrapper."""
            daprWfContext = DaprWorkflowContext(ctx)
            if inp is None:
                return fn(daprWfContext)
            return fn(daprWfContext, inp)

        if hasattr(fn, '_registered_name'):
            raise ValueError(f'Workflow {fn.__name__} already registered as {fn._registered_name}')
        fn.__dict__['_registered_name'] = name if name else fn.__name__

        if name:
            self.__worker._registry.add_named_orchestrator(name, orchestrationWrapper)
            return
        self.__worker._registry.add_named_orchestrator(fn.__name__, orchestrationWrapper)

    def register_activity(self, fn: Activity, *, name: Optional[str] = None):
        """Registers a workflow activity as a function that takes
           a specified input type and returns a specified output type.
        """
        def activityWrapper(ctx: task.ActivityContext, inp: Optional[TInput] = None):
            """Responsible to call Activity function in activityWrapper"""
            wfActivityContext = WorkflowActivityContext(ctx)
            if inp is None:
                return fn(wfActivityContext)
            return fn(wfActivityContext, inp)

        if hasattr(fn, '_registered_name'):
            raise ValueError(f'Activity {fn.__name__} already registered as {fn._registered_name}')
        fn.__dict__['_registered_name'] = name if name else fn.__name__

        if name:
            self.__worker._registry.add_named_activity(name, activityWrapper)
            return
        self.__worker._registry.add_named_activity(fn.__name__, activityWrapper)

    def start(self):
        """Starts the listening for work items on a background thread."""
        self.__worker.start()

    def shutdown(self):
        """Stops the listening for work items on a background thread."""
        self.__worker.stop()

    def workflow(self, __fn: Workflow = None, *, name: Optional[str] = None):
        """Decorator to register a workflow function.

        This example shows how to register a workflow function with a name:

                from dapr.ext.workflow import WorkflowRuntime
                wfr = WorkflowRuntime()

                @wfr.workflow(name="add")
                def add(ctx, x: int, y: int) -> int:
                    return x + y

        This example shows how to register a workflow function without a name:

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

            innerfn.__dict__['_registered_name'] = name if name else fn.__name__
            innerfn.__signature__ = inspect.signature(fn)
            return innerfn

        if __fn:
            # This case is true when the decorator is used without arguments
            # and the function to be decorated is passed as the first argument.
            return wrapper(__fn)

        return wrapper

    def activity(self, __fn: Activity = None, *, name: Optional[str] = None):
        """Decorator to register an activity function.

        This example shows how to register an activity function with a name:

            from dapr.ext.workflow import WorkflowRuntime
            wfr = WorkflowRuntime()

            @wfr.activity(name="add")
            def add(ctx, x: int, y: int) -> int:
                return x + y

        This example shows how to register an activity function without a name:

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

            innerfn.__dict__['_registered_name'] = name if name else fn.__name__
            innerfn.__signature__ = inspect.signature(fn)
            return innerfn

        if __fn:
            # This case is true when the decorator is used without arguments
            # and the function to be decorated is passed as the first argument.
            return wrapper(__fn)

        return wrapper
