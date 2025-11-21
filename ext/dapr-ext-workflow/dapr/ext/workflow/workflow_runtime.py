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
import traceback
from functools import wraps
from typing import Any, Awaitable, Callable, List, Optional, Sequence, TypeVar, Union

import grpc
from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext, Handlers
from dapr.ext.workflow.execution_info import ActivityExecutionInfo, WorkflowExecutionInfo
from dapr.ext.workflow.interceptors import (
    CallActivityRequest,
    CallChildWorkflowRequest,
    ExecuteActivityRequest,
    ExecuteWorkflowRequest,
    RuntimeInterceptor,
    WorkflowOutboundInterceptor,
    compose_runtime_chain,
    compose_workflow_outbound_chain,
    unwrap_payload_with_metadata,
    wrap_payload_with_metadata,
)
from dapr.ext.workflow.logger import Logger, LoggerOptions
from dapr.ext.workflow.util import getAddress
from dapr.ext.workflow.workflow_activity_context import Activity, WorkflowActivityContext
from dapr.ext.workflow.workflow_context import Workflow
from durabletask import task, worker
from durabletask.aio.sandbox import SandboxMode

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
        host: str | None = None,
        port: str | None = None,
        logger_options: Optional[LoggerOptions] = None,
        interceptors: Optional[Sequence[ClientInterceptor]] = None,
        maximum_concurrent_activity_work_items: Optional[int] = None,
        maximum_concurrent_orchestration_work_items: Optional[int] = None,
        maximum_thread_pool_workers: Optional[int] = None,
        *,
        runtime_interceptors: Optional[list[RuntimeInterceptor]] = None,
        workflow_outbound_interceptors: Optional[list[WorkflowOutboundInterceptor]] = None,
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
            interceptors=interceptors,
            concurrency_options=worker.ConcurrencyOptions(
                maximum_concurrent_activity_work_items=maximum_concurrent_activity_work_items,
                maximum_concurrent_orchestration_work_items=maximum_concurrent_orchestration_work_items,
                maximum_thread_pool_workers=maximum_thread_pool_workers,
            ),
        )
        # Interceptors
        self._runtime_interceptors: List[RuntimeInterceptor] = list(runtime_interceptors or [])
        self._workflow_outbound_interceptors: List[WorkflowOutboundInterceptor] = list(
            workflow_outbound_interceptors or []
        )

    # Outbound helpers apply interceptors and wrap metadata; no built-in transformations.
    def _apply_outbound_activity(
        self,
        ctx: Any,
        activity: Callable[..., Any] | str,
        input: Any,
        retry_policy: Any | None,
        metadata: dict[str, str] | None = None,
    ):
        # Build workflow-outbound chain to transform CallActivityRequest
        name = (
            activity
            if isinstance(activity, str)
            else (
                activity.__dict__['_dapr_alternate_name']
                if hasattr(activity, '_dapr_alternate_name')
                else activity.__name__
            )
        )

        def terminal(term_req: CallActivityRequest) -> CallActivityRequest:
            return term_req

        chain = compose_workflow_outbound_chain(self._workflow_outbound_interceptors, terminal)
        # Use per-context default metadata when not provided
        metadata = metadata or ctx.get_metadata()
        act_req = CallActivityRequest(
            activity_name=name,
            input=input,
            retry_policy=retry_policy,
            workflow_ctx=ctx,
            metadata=metadata,
        )
        out = chain(act_req)
        if isinstance(out, CallActivityRequest):
            return wrap_payload_with_metadata(out.input, out.metadata)
        return input

    def _apply_outbound_child(
        self,
        ctx: Any,
        workflow: Callable[..., Any] | str,
        input: Any,
        metadata: dict[str, str] | None = None,
    ):
        name = (
            workflow
            if isinstance(workflow, str)
            else (
                workflow.__dict__['_dapr_alternate_name']
                if hasattr(workflow, '_dapr_alternate_name')
                else workflow.__name__
            )
        )

        def terminal(term_req: CallChildWorkflowRequest) -> CallChildWorkflowRequest:
            return term_req

        chain = compose_workflow_outbound_chain(self._workflow_outbound_interceptors, terminal)
        metadata = metadata or ctx.get_metadata()
        child_req = CallChildWorkflowRequest(
            workflow_name=name, input=input, instance_id=None, workflow_ctx=ctx, metadata=metadata
        )
        out = chain(child_req)
        if isinstance(out, CallChildWorkflowRequest):
            return wrap_payload_with_metadata(out.input, out.metadata)
        return input

    def _apply_outbound_continue_as_new(
        self,
        ctx: Any,
        new_input: Any,
        metadata: dict[str, str] | None = None,
    ):
        # Build workflow-outbound chain to transform ContinueAsNewRequest
        from dapr.ext.workflow.interceptors import ContinueAsNewRequest

        def terminal(term_req: ContinueAsNewRequest) -> ContinueAsNewRequest:
            return term_req

        chain = compose_workflow_outbound_chain(self._workflow_outbound_interceptors, terminal)
        metadata = metadata or ctx.get_metadata()
        cnr = ContinueAsNewRequest(input=new_input, workflow_ctx=ctx, metadata=metadata)
        out = chain(cnr)
        if isinstance(out, ContinueAsNewRequest):
            return wrap_payload_with_metadata(out.input, out.metadata)
        return new_input

    def register_workflow(self, fn: Workflow, *, name: Optional[str] = None):
        # Seamlessly support async workflows using the existing API
        if inspect.iscoroutinefunction(fn):
            return self.register_async_workflow(fn, name=name)

        self._logger.info(f"Registering workflow '{fn.__name__}' with runtime")

        def orchestration_wrapper(ctx: task.OrchestrationContext, inp: Optional[TInput] = None):
            """Orchestration entrypoint wrapped by runtime interceptors."""
            payload, md = unwrap_payload_with_metadata(inp)
            dapr_wf_context = self._get_workflow_context(ctx, md)

            # Build interceptor chain; terminal calls the user function (generator or non-generator)
            def final_handler(exec_req: ExecuteWorkflowRequest) -> Any:
                try:
                    return (
                        fn(dapr_wf_context)
                        if exec_req.input is None
                        else fn(dapr_wf_context, exec_req.input)
                    )
                except Exception as exc:  # log and re-raise to surface failure details
                    self._logger.error(
                        f"{ctx.instance_id}: workflow '{fn.__name__}' raised {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                    )
                    raise

            chain = compose_runtime_chain(self._runtime_interceptors, final_handler)
            return chain(ExecuteWorkflowRequest(ctx=dapr_wf_context, input=payload, metadata=md))

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
            fn.__dict__['_dapr_alternate_name'], orchestration_wrapper
        )
        fn.__dict__['_workflow_registered'] = True

    def register_activity(self, fn: Activity, *, name: Optional[str] = None):
        """Registers a workflow activity as a function that takes
        a specified input type and returns a specified output type.
        """
        self._logger.info(f"Registering activity '{fn.__name__}' with runtime")

        def activity_wrapper(ctx: task.ActivityContext, inp: Optional[TInput] = None):
            """Activity entrypoint wrapped by runtime interceptors."""
            wf_activity_context = WorkflowActivityContext(ctx)
            payload, md = unwrap_payload_with_metadata(inp)
            # Populate inbound metadata onto activity context
            wf_activity_context.set_metadata(md or {})

            # Populate execution info
            try:
                # Determine activity name (registered alternate name or function __name__)
                act_name = getattr(fn, '_dapr_alternate_name', fn.__name__)
                ainfo = ActivityExecutionInfo(inbound_metadata=md or {}, activity_name=act_name)
                wf_activity_context._set_execution_info(ainfo)
            except Exception:
                pass

            def final_handler(exec_req: ExecuteActivityRequest) -> Any:
                try:
                    # Support async and sync activities
                    if inspect.iscoroutinefunction(fn):
                        if exec_req.input is None:
                            return asyncio.run(fn(wf_activity_context))
                        return asyncio.run(fn(wf_activity_context, exec_req.input))
                    if exec_req.input is None:
                        return fn(wf_activity_context)
                    return fn(wf_activity_context, exec_req.input)
                except Exception as exc:
                    # Log details for troubleshooting (metadata, error type)
                    self._logger.error(
                        f"{ctx.orchestration_id}:{ctx.task_id} activity '{fn.__name__}' failed with {type(exc).__name__}: {exc}"
                    )
                    self._logger.error(traceback.format_exc())
                    raise

            chain = compose_runtime_chain(self._runtime_interceptors, final_handler)
            return chain(
                ExecuteActivityRequest(ctx=wf_activity_context, input=payload, metadata=md)
            )

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
            fn.__dict__['_dapr_alternate_name'], activity_wrapper
        )
        fn.__dict__['_activity_registered'] = True

    def start(self):
        """Starts the listening for work items on a background thread."""
        self.__worker.start()

    def __enter__(self):
        self.start()
        return self

    def shutdown(self):
        """Stops the listening for work items on a background thread."""
        try:
            self._logger.info('Stopping gRPC worker...')
            self.__worker.stop()
            self._logger.info('Worker shutdown completed')
        except Exception as exc:  # pragma: no cover
            # DurableTask worker may emit CANCELLED warnings during local shutdown; not fatal
            self._logger.warning(f'Worker stop encountered {type(exc).__name__}: {exc}')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

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
        sandbox_mode: SandboxMode = SandboxMode.BEST_EFFORT,
    ) -> None:
        """Register an async workflow function.

        The async workflow is wrapped by a coroutine-to-generator driver so it can be
        executed by the Durable Task runtime alongside existing generator workflows.

        Args:
            fn: The async workflow function, taking ``AsyncWorkflowContext`` and optional input.
            name: Optional alternate name for registration.
            sandbox_mode: Scoped compatibility patching mode.
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
            """Orchestration entrypoint wrapped by runtime interceptors."""
            payload, md = unwrap_payload_with_metadata(inp)
            base_ctx = self._get_workflow_context(ctx, md)

            async_ctx = AsyncWorkflowContext(base_ctx)

            def final_handler(exec_req: ExecuteWorkflowRequest) -> Any:
                # Build the generator using the (potentially shaped) input from interceptors.
                shaped_input = exec_req.input
                return runner.to_generator(async_ctx, shaped_input)

            chain = compose_runtime_chain(self._runtime_interceptors, final_handler)
            return chain(ExecuteWorkflowRequest(ctx=async_ctx, input=payload, metadata=md))

        self.__worker._registry.add_named_orchestrator(
            fn.__dict__['_dapr_alternate_name'], generator_orchestrator
        )
        fn.__dict__['_workflow_registered'] = True

    def _get_workflow_context(
        self, ctx: task.OrchestrationContext, metadata: dict[str, str] | None = None
    ) -> DaprWorkflowContext:
        """Get the workflow context and execution info for the given orchestration context and metadata.
           Execution info serves as a read-only snapshot of the workflow context.

        Args:
            ctx: The orchestration context.
            metadata: The metadata for the workflow.

        Returns:
            The workflow context.
        """
        base_ctx = DaprWorkflowContext(
            ctx,
            self._logger.get_options(),
            outbound_handlers={
                Handlers.CALL_ACTIVITY: self._apply_outbound_activity,
                Handlers.CALL_CHILD_WORKFLOW: self._apply_outbound_child,
                Handlers.CONTINUE_AS_NEW: self._apply_outbound_continue_as_new,
            },
        )
        # Populate minimal execution info (only inbound metadata)
        info = WorkflowExecutionInfo(inbound_metadata=metadata or {})
        base_ctx._set_execution_info(info)
        base_ctx.set_metadata(metadata or {})
        return base_ctx

    def async_workflow(
        self,
        __fn: Callable[[AsyncWorkflowContext, Any], Awaitable[Any]] = None,
        *,
        name: Optional[str] = None,
        sandbox_mode: SandboxMode = SandboxMode.OFF,
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
