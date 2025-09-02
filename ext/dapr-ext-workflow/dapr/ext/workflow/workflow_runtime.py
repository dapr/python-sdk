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
from typing import Any, Awaitable, Callable, List, Optional, Tuple, TypeVar

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
from dapr.ext.workflow.middleware import (
    MiddlewareOrder,
    MiddlewarePolicy,
    RuntimeMiddleware,
)
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
        middleware: Optional[list[RuntimeMiddleware]] = None,
        middleware_policy: str = MiddlewarePolicy.CONTINUE_ON_ERROR,
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
        # Middleware state
        self._middleware: List[Tuple[int, RuntimeMiddleware]] = []
        self._middleware_policy: str = middleware_policy
        if middleware:
            for mw in middleware:
                self.add_middleware(mw)

    # Middleware API
    def add_middleware(self, mw: RuntimeMiddleware, *, order: int = MiddlewareOrder.DEFAULT) -> None:
        self._middleware.append((order, mw))
        # Keep sorted by order
        self._middleware.sort(key=lambda x: x[0])

    def remove_middleware(self, mw: RuntimeMiddleware) -> None:
        self._middleware = [(o, m) for (o, m) in self._middleware if m is not mw]

    def set_middleware_policy(self, policy: str) -> None:
        self._middleware_policy = policy

    # Internal helpers to invoke middleware hooks
    def _iter_mw_start(self):
        # Ascending order
        return [m for _, m in self._middleware]

    def _iter_mw_end(self):
        # Descending order
        return [m for _, m in reversed(self._middleware)]

    def _invoke_hook(self, hook_name: str, *, ctx: Any, arg: Any, end_phase: bool, allow_async: bool) -> None:
        middlewares = self._iter_mw_end() if end_phase else self._iter_mw_start()
        for mw in middlewares:
            hook = getattr(mw, hook_name, None)
            if not hook:
                continue
            try:
                maybe = hook(ctx, arg)
                # Avoid awaiting inside orchestrator; only allow async in activity wrappers
                if allow_async and asyncio.iscoroutine(maybe):
                    asyncio.run(maybe)
            except BaseException as exc:
                if self._middleware_policy == MiddlewarePolicy.RAISE_ON_ERROR:
                    raise
                # CONTINUE_ON_ERROR: log and continue
                try:
                    self._logger.warning(
                        f"Middleware hook '{hook_name}' failed in {mw.__class__.__name__}: {exc}"
                    )
                except Exception:
                    pass

    # Outbound transformation helpers (workflow context)
    def _apply_outbound_activity(self, ctx: Any, activity: Callable[..., Any] | str, input: Any, retry_policy: Any | None):  # noqa: E501
        value = input
        for _, mw in self._middleware:
            hook = getattr(mw, 'on_schedule_activity', None)
            if not hook:
                continue
            try:
                value = hook(ctx, activity, value, retry_policy)
            except BaseException as exc:
                if self._middleware_policy == MiddlewarePolicy.RAISE_ON_ERROR:
                    raise
                try:
                    self._logger.warning(
                        f"Middleware hook 'on_schedule_activity' failed in {mw.__class__.__name__}: {exc}"
                    )
                except Exception:
                    pass
        return value

    def _apply_outbound_child(self, ctx: Any, workflow: Callable[..., Any] | str, input: Any):
        value = input
        for _, mw in self._middleware:
            hook = getattr(mw, 'on_start_child_workflow', None)
            if not hook:
                continue
            try:
                value = hook(ctx, workflow, value)
            except BaseException as exc:
                if self._middleware_policy == MiddlewarePolicy.RAISE_ON_ERROR:
                    raise
                try:
                    self._logger.warning(
                        f"Middleware hook 'on_start_child_workflow' failed in {mw.__class__.__name__}: {exc}"
                    )
                except Exception:
                    pass
        return value

    def register_workflow(self, fn: Workflow, *, name: Optional[str] = None):
        # Seamlessly support async workflows using the existing API
        if inspect.iscoroutinefunction(fn):
            return self.register_async_workflow(fn, name=name)

        self._logger.info(f"Registering workflow '{fn.__name__}' with runtime")

        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: Optional[TInput] = None):
            """Responsible to call Workflow function in orchestrationWrapper with middleware hooks."""
            daprWfContext = DaprWorkflowContext(
                ctx,
                self._logger.get_options(),
                outbound_handlers={
                    'activity': self._apply_outbound_activity,
                    'child': self._apply_outbound_child,
                },
            )

            # on_workflow_start
            self._invoke_hook('on_workflow_start', ctx=daprWfContext, arg=inp, end_phase=False, allow_async=False)

            try:
                result_or_gen = fn(daprWfContext) if inp is None else fn(daprWfContext, inp)
            except BaseException as call_exc:
                # on_workflow_error
                self._invoke_hook('on_workflow_error', ctx=daprWfContext, arg=call_exc, end_phase=True, allow_async=False)
                raise

            # If the workflow returned a generator, wrap it to intercept yield/resume
            if inspect.isgenerator(result_or_gen):
                gen = result_or_gen

                def driver():
                    sent_value: Any = None
                    try:
                        while True:
                            yielded = gen.send(sent_value)
                            # on_workflow_yield
                            self._invoke_hook('on_workflow_yield', ctx=daprWfContext, arg=yielded, end_phase=False, allow_async=False)
                            sent_value = yield yielded
                            # on_workflow_resume
                            self._invoke_hook('on_workflow_resume', ctx=daprWfContext, arg=sent_value, end_phase=False, allow_async=False)
                    except StopIteration as stop:
                        # on_workflow_complete
                        self._invoke_hook('on_workflow_complete', ctx=daprWfContext, arg=stop.value, end_phase=True, allow_async=False)
                        return stop.value
                    except BaseException as exc:
                        # on_workflow_error
                        self._invoke_hook('on_workflow_error', ctx=daprWfContext, arg=exc, end_phase=True, allow_async=False)
                        raise

                return driver()

            # Non-generator result: completed synchronously
            self._invoke_hook('on_workflow_complete', ctx=daprWfContext, arg=result_or_gen, end_phase=True, allow_async=False)
            return result_or_gen

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
            """Responsible to call Activity function in activityWrapper with middleware hooks."""
            wfActivityContext = WorkflowActivityContext(ctx)

            # on_activity_start (allow awaiting)
            self._invoke_hook('on_activity_start', ctx=wfActivityContext, arg=inp, end_phase=False, allow_async=True)

            try:
                # Seamless support for async activities
                if inspect.iscoroutinefunction(fn):
                    if inp is None:
                        result = asyncio.run(fn(wfActivityContext))
                    else:
                        result = asyncio.run(fn(wfActivityContext, inp))
                else:
                    if inp is None:
                        result = fn(wfActivityContext)
                    else:
                        result = fn(wfActivityContext, inp)
            except BaseException as act_exc:
                # on_activity_error (allow awaiting)
                self._invoke_hook('on_activity_error', ctx=wfActivityContext, arg=act_exc, end_phase=True, allow_async=True)
                raise

            # on_activity_complete (allow awaiting)
            self._invoke_hook('on_activity_complete', ctx=wfActivityContext, arg=result, end_phase=True, allow_async=True)
            return result

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
            # on_workflow_start
            self._invoke_hook('on_workflow_start', ctx=async_ctx, arg=inp, end_phase=False, allow_async=False)

            gen = runner.to_generator(async_ctx, inp)
            result = None
            try:
                while True:
                    t = gen.send(result)
                    # on_workflow_yield
                    self._invoke_hook('on_workflow_yield', ctx=async_ctx, arg=t, end_phase=False, allow_async=False)
                    result = yield t
                    # on_workflow_resume
                    self._invoke_hook('on_workflow_resume', ctx=async_ctx, arg=result, end_phase=False, allow_async=False)
            except StopIteration as stop:
                # on_workflow_complete
                self._invoke_hook('on_workflow_complete', ctx=async_ctx, arg=stop.value, end_phase=True, allow_async=False)
                return stop.value
            except BaseException as exc:
                # on_workflow_error
                self._invoke_hook('on_workflow_error', ctx=async_ctx, arg=exc, end_phase=True, allow_async=False)
                raise

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
