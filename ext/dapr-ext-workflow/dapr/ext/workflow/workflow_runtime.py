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
import asyncio
from typing import Optional, TypeVar, Awaitable, Callable, Any

try:
    from typing import Literal  # py39+
except ImportError:  # pragma: no cover
    Literal = str  # type: ignore

from durabletask import task, worker

from dapr.clients import DaprInternalError
from dapr.clients.http.client import DAPR_API_TOKEN_HEADER
from dapr.conf import settings
from dapr.conf.helpers import GrpcEndpoint
from dapr.ext.workflow.async_context import AsyncWorkflowContext
from dapr.ext.workflow.async_driver import CoroutineOrchestratorRunner
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.logger import Logger, LoggerOptions
from dapr.ext.workflow.util import getAddress
from dapr.ext.workflow.workflow_activity_context import Activity, WorkflowActivityContext
from dapr.ext.workflow.workflow_context import Workflow

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowRuntime:
    """WorkflowRuntime is the entry point for registering workflows and activities."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[str] = None,
        logger_options: Optional[LoggerOptions] = None,
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
        )

    def register_workflow(self, fn: Workflow, *, name: Optional[str] = None):
        # Seamlessly support async workflows using the existing API
        if inspect.iscoroutinefunction(fn):
            return self.register_async_workflow(fn, name=name)

        self._logger.info(f"Registering workflow '{fn.__name__}' with runtime")

        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: Optional[TInput] = None):
            """Responsible to call Workflow function in orchestrationWrapper"""
            daprWfContext = DaprWorkflowContext(ctx, self._logger.get_options())
            if inp is None:
                return fn(daprWfContext)
            return fn(daprWfContext, inp)

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
            wfActivityContext = WorkflowActivityContext(ctx)
            # Seamless support for async activities
            if inspect.iscoroutinefunction(fn):
                if inp is None:
                    return asyncio.run(fn(wfActivityContext))
                return asyncio.run(fn(wfActivityContext, inp))
            if inp is None:
                return fn(wfActivityContext)
            return fn(wfActivityContext, inp)

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

    def start(self):
        """Starts the listening for work items on a background thread."""
        self.__worker.start()

    def shutdown(self):
        """Stops the listening for work items on a background thread."""
        self.__worker.stop()

    def wait_for_ready(self, timeout: Optional[float] = None) -> None:
        """Optionally block until the underlying worker is connected and ready.

        If the durable task worker supports a readiness API, this will delegate to it. Otherwise it is a no-op.

        Args:
            timeout: Optional timeout in seconds.
        """
        if hasattr(self.__worker, 'wait_for_ready'):
            try:
                # type: ignore[attr-defined]
                self.__worker.wait_for_ready(timeout=timeout)
            except TypeError:
                # Some implementations may not accept named arg
                self.__worker.wait_for_ready(timeout)  # type: ignore[misc]

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
            # Auto-detect coroutine and delegate to async registration
            if inspect.iscoroutinefunction(fn):
                self.register_async_workflow(fn, name=name)
            else:
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

    # Async orchestrator registration (additive)
    def register_async_workflow(
        self,
        fn: Callable[[AsyncWorkflowContext, Any], Awaitable[Any]],
        *,
        name: Optional[str] = None,
        sandbox_mode: Literal['off', 'best_effort', 'strict'] = 'off',
    ) -> None:
        """Register an async workflow function.

        The async workflow is wrapped by a coroutine-to-generator driver so it can be
        executed by the Durable Task runtime alongside existing generator workflows.

        Args:
            fn: The async workflow function, taking ``AsyncWorkflowContext`` and optional input.
            name: Optional alternate name for registration.
            sandbox_mode: Scoped compatibility patching mode: "off" (default), "best_effort", or "strict".
        """
        self._logger.info(f"Registering ASYNC workflow '{fn.__name__}' with runtime")

        if hasattr(fn, '_workflow_registered'):
            alt_name = fn.__dict__['_dapr_alternate_name']
            raise ValueError(f'Workflow {fn.__name__} already registered as {alt_name}')
        if hasattr(fn, '_dapr_alternate_name'):
            alt_name = fn._dapr_alternate_name
            if name is not None:
                m = f'Workflow {fn.__name__} already has an alternate name {alt_name}'
                raise ValueError(m)
        else:
            fn.__dict__['_dapr_alternate_name'] = name if name else fn.__name__

        runner = CoroutineOrchestratorRunner(fn, sandbox_mode=sandbox_mode)

        def generator_orchestrator(ctx: task.OrchestrationContext, inp: Optional[Any] = None):
            async_ctx = AsyncWorkflowContext(DaprWorkflowContext(ctx, self._logger.get_options()))
            gen = runner.to_generator(async_ctx, inp)
            result = None
            try:
                while True:
                    t = gen.send(result)
                    result = yield t
            except StopIteration as stop:
                return stop.value

        self.__worker._registry.add_named_orchestrator(
            fn.__dict__['_dapr_alternate_name'], generator_orchestrator
        )
        fn.__dict__['_workflow_registered'] = True

    def async_workflow(
        self,
        __fn: Callable[[AsyncWorkflowContext, Any], Awaitable[Any]] = None,
        *,
        name: Optional[str] = None,
        sandbox_mode: Literal['off', 'best_effort', 'strict'] = 'off',
    ):
        """Decorator to register an async workflow function.

        Usage:
            @runtime.async_workflow(name="my_wf")
            async def my_wf(ctx: AsyncWorkflowContext, input):
                ...
        """

        def wrapper(fn: Callable[[AsyncWorkflowContext, Any], Awaitable[Any]]):
            self.register_async_workflow(fn, name=name, sandbox_mode=sandbox_mode)

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
