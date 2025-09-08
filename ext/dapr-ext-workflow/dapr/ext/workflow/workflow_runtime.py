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

import asyncio
import inspect
from functools import wraps
from typing import Any, Awaitable, Callable, List, Optional, TypeVar

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
from dapr.ext.workflow.interceptors import (
    ClientInterceptor,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    RuntimeInterceptor,
    StartActivityInput,
    StartChildInput,
    compose_client_chain,
    compose_runtime_chain,
)
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
        *,
        interceptors: Optional[list[RuntimeInterceptor]] = None,
        client_interceptors: Optional[list[ClientInterceptor]] = None,
    ):
        self._logger = Logger('WorkflowRuntime', logger_options)
        metadata = ()
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
        # Interceptors
        self._runtime_interceptors: List[RuntimeInterceptor] = list(interceptors or [])
        self._client_interceptors: List[ClientInterceptor] = list(client_interceptors or [])
    # Outbound transformation helpers (workflow context) — pass-throughs now
    def _apply_outbound_activity(
        self, ctx: Any, activity: Callable[..., Any] | str, input: Any, retry_policy: Any | None
    ):
        # Build a transform-only client chain that returns the mutated StartActivityInput
        name = (
            activity
            if isinstance(activity, str)
            else (
                activity.__dict__['_dapr_alternate_name']
                if hasattr(activity, '_dapr_alternate_name')
                else activity.__name__
            )
        )
        def terminal(term_input: StartActivityInput) -> StartActivityInput:
            return term_input
        chain = compose_client_chain(self._client_interceptors, terminal)
        sai = StartActivityInput(activity_name=name, args=input, retry_policy=retry_policy)
        out = chain(sai)
        return out.args if isinstance(out, StartActivityInput) else input

    def _apply_outbound_child(self, ctx: Any, workflow: Callable[..., Any] | str, input: Any):
        name = (
            workflow
            if isinstance(workflow, str)
            else (
                workflow.__dict__['_dapr_alternate_name']
                if hasattr(workflow, '_dapr_alternate_name')
                else workflow.__name__
            )
        )
        def terminal(term_input: StartChildInput) -> StartChildInput:
            return term_input
        chain = compose_client_chain(self._client_interceptors, terminal)
        sci = StartChildInput(workflow_name=name, args=input, instance_id=None)
        out = chain(sci)
        return out.args if isinstance(out, StartChildInput) else input

    def register_workflow(self, fn: Workflow, *, name: Optional[str] = None):
        # Seamlessly support async workflows using the existing API
        if inspect.iscoroutinefunction(fn):
            return self.register_async_workflow(fn, name=name)

        self._logger.info(f"Registering workflow '{fn.__name__}' with runtime")

        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: Optional[TInput] = None):
            """Orchestration entrypoint wrapped by runtime interceptors."""
            daprWfContext = DaprWorkflowContext(
                ctx,
                self._logger.get_options(),
                outbound_handlers={
                    'activity': self._apply_outbound_activity,
                    'child': self._apply_outbound_child,
                },
            )
            # Build interceptor chain; terminal calls the user function (generator or non-generator)
            def terminal(e_input: ExecuteWorkflowInput) -> Any:
                result_or_gen = (
                    fn(daprWfContext)
                    if e_input.input is None
                    else fn(daprWfContext, e_input.input)
                )
                if inspect.isgenerator(result_or_gen):
                    return result_or_gen
                return result_or_gen
            chain = compose_runtime_chain(self._runtime_interceptors, terminal)
            return chain(ExecuteWorkflowInput(ctx=daprWfContext, input=inp))

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
            """Activity entrypoint wrapped by runtime interceptors."""
            wfActivityContext = WorkflowActivityContext(ctx)

            def terminal(e_input: ExecuteActivityInput) -> Any:
                # Support async and sync activities
                if inspect.iscoroutinefunction(fn):
                    if e_input.input is None:
                        return asyncio.run(fn(wfActivityContext))
                    return asyncio.run(fn(wfActivityContext, e_input.input))
                if e_input.input is None:
                    return fn(wfActivityContext)
                return fn(wfActivityContext, e_input.input)

            chain = compose_runtime_chain(self._runtime_interceptors, terminal)
            return chain(ExecuteActivityInput(ctx=wfActivityContext, input=inp))

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
            async_ctx = AsyncWorkflowContext(
                DaprWorkflowContext(
                    ctx,
                    self._logger.get_options(),
                    outbound_handlers={
                        'activity': self._apply_outbound_activity,
                        'child': self._apply_outbound_child,
                    },
                )
            )
            gen = runner.to_generator(async_ctx, inp)
            def terminal(e_input: ExecuteWorkflowInput) -> Any:
                # Return the generator for the durable runtime to drive
                return gen
            chain = compose_runtime_chain(self._runtime_interceptors, terminal)
            return chain(ExecuteWorkflowInput(ctx=async_ctx, input=inp))

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
