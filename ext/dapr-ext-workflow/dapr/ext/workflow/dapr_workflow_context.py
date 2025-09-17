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
import enum
from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional, TypeVar, Union

from durabletask import task

from dapr.ext.workflow.deterministic import DeterministicContextMixin
from dapr.ext.workflow.execution_info import WorkflowExecutionInfo
from dapr.ext.workflow.logger import Logger, LoggerOptions
from dapr.ext.workflow.retry_policy import RetryPolicy
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_context import Workflow, WorkflowContext

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class Handlers(enum.Enum):
    CALL_ACTIVITY = 'call_activity'
    CALL_CHILD_WORKFLOW = 'call_child_workflow'


class DaprWorkflowContext(WorkflowContext, DeterministicContextMixin):
    """DaprWorkflowContext that provides proxy access to internal OrchestrationContext instance."""

    def __init__(
        self,
        ctx: task.OrchestrationContext,
        logger_options: Optional[LoggerOptions] = None,
        *,
        outbound_handlers: Optional[dict[Handlers, Any]] = None,
    ):
        self.__obj = ctx
        self._logger = Logger('DaprWorkflowContext', logger_options)
        self._outbound_handlers = outbound_handlers or {}
        self._metadata: dict[str, str] | None = None

    # provide proxy access to regular attributes of wrapped object
    def __getattr__(self, name):
        return getattr(self.__obj, name)

    @property
    def instance_id(self) -> str:
        return self.__obj.instance_id

    @property
    def current_utc_datetime(self) -> datetime:
        return self.__obj.current_utc_datetime

    @property
    def is_replaying(self) -> bool:
        return self.__obj.is_replaying

    # Deterministic utilities are provided by mixin (now, random, uuid4, new_guid)

    # Tracing (engine-provided) pass-throughs when available
    @property
    def trace_parent(self) -> str | None:
        return self.__obj.trace_parent

    @property
    def trace_state(self) -> str | None:
        return self.__obj.trace_state

    @property
    def workflow_span_id(self) -> str | None:
        # provided by durabletask; naming aligned to workflow
        return self.__obj.orchestration_span_id

    # Metadata API
    def set_metadata(self, metadata: dict[str, str] | None) -> None:
        self._metadata = dict(metadata) if metadata else None

    def get_metadata(self) -> dict[str, str] | None:
        return dict(self._metadata) if self._metadata else None

    # Header aliases (ergonomic alias for users familiar with Temporal terminology)
    def set_headers(self, headers: dict[str, str] | None) -> None:
        self.set_metadata(headers)

    def get_headers(self) -> dict[str, str] | None:
        return self.get_metadata()

    def set_custom_status(self, custom_status: str) -> None:
        self._logger.debug(f'{self.instance_id}: Setting custom status to {custom_status}')
        self.__obj.set_custom_status(custom_status)

    # Execution info (populated by runtime when available)
    @property
    def execution_info(self) -> WorkflowExecutionInfo | None:
        return getattr(self, '_execution_info', None)

    def _set_execution_info(self, info: WorkflowExecutionInfo) -> None:
        self._execution_info = info

    def create_timer(self, fire_at: Union[datetime, timedelta]) -> task.Task:
        self._logger.debug(f'{self.instance_id}: Creating timer to fire at {fire_at} time')
        return self.__obj.create_timer(fire_at)

    def call_activity(
        self,
        activity: Callable[[WorkflowActivityContext, TInput], TOutput],
        *,
        input: TInput = None,
        retry_policy: Optional[RetryPolicy] = None,
        metadata: dict[str, str] | None = None,
    ) -> task.Task[TOutput]:
        self._logger.debug(f'{self.instance_id}: Creating activity {activity.__name__}')
        if hasattr(activity, '_dapr_alternate_name'):
            act = activity.__dict__['_dapr_alternate_name']
        else:
            # this case should ideally never happen
            act = activity.__name__
        # Apply outbound client interceptor transformations if provided via runtime wiring
        transformed_input: Any = input
        if Handlers.CALL_ACTIVITY in self._outbound_handlers and callable(
            self._outbound_handlers[Handlers.CALL_ACTIVITY]
        ):
            transformed_input = self._outbound_handlers[Handlers.CALL_ACTIVITY](
                self, activity, input, retry_policy, metadata or self.get_metadata()
            )
        if retry_policy is None:
            return self.__obj.call_activity(activity=act, input=transformed_input)
        return self.__obj.call_activity(
            activity=act, input=transformed_input, retry_policy=retry_policy.obj
        )

    def call_child_workflow(
        self,
        workflow: Workflow,
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
        metadata: dict[str, str] | None = None,
    ) -> task.Task[TOutput]:
        self._logger.debug(f'{self.instance_id}: Creating child workflow {workflow.__name__}')

        def wf(ctx: task.OrchestrationContext, inp: TInput):
            dapr_wf_context = DaprWorkflowContext(ctx, self._logger.get_options())
            return workflow(dapr_wf_context, inp)

        # copy workflow name so durabletask.worker can find the orchestrator in its registry

        if hasattr(workflow, '_dapr_alternate_name'):
            wf.__name__ = workflow.__dict__['_dapr_alternate_name']
        else:
            # this case should ideally never happen
            wf.__name__ = workflow.__name__
        # Apply outbound client interceptor transformations if provided via runtime wiring
        transformed_input: Any = input
        if Handlers.CALL_CHILD_WORKFLOW in self._outbound_handlers and callable(
            self._outbound_handlers[Handlers.CALL_CHILD_WORKFLOW]
        ):
            transformed_input = self._outbound_handlers[Handlers.CALL_CHILD_WORKFLOW](
                self, workflow, input, metadata or self.get_metadata()
            )
        if retry_policy is None:
            return self.__obj.call_sub_orchestrator(
                wf, input=transformed_input, instance_id=instance_id
            )
        return self.__obj.call_sub_orchestrator(
            wf, input=transformed_input, instance_id=instance_id, retry_policy=retry_policy.obj
        )

    def wait_for_external_event(self, name: str) -> task.Task:
        self._logger.debug(f'{self.instance_id}: Waiting for external event {name}')
        return self.__obj.wait_for_external_event(name)

    def continue_as_new(
        self,
        new_input: Any,
        *,
        save_events: bool = False,
        carryover_metadata: bool | dict[str, str] = False,
        carryover_headers: bool | dict[str, str] | None = None,
    ) -> None:
        self._logger.debug(f'{self.instance_id}: Continuing as new')
        # Merge/carry metadata if requested
        payload = new_input
        effective_carryover = (
            carryover_headers if carryover_headers is not None else carryover_metadata
        )
        if effective_carryover:
            base = self.get_metadata() or {}
            if isinstance(effective_carryover, dict):
                md = {**base, **effective_carryover}
            else:
                md = base
            from dapr.ext.workflow.interceptors import wrap_payload_with_metadata

            payload = wrap_payload_with_metadata(new_input, md)
        self.__obj.continue_as_new(payload, save_events=save_events)


def when_all(tasks: List[task.Task[T]]) -> task.WhenAllTask[T]:
    """Returns a task that completes when all of the provided tasks complete or when one of the
    tasks fail."""
    return task.when_all(tasks)


def when_any(tasks: List[task.Task]) -> task.WhenAnyTask:
    """Returns a task that completes when any of the provided tasks complete or fail."""
    return task.when_any(tasks)
