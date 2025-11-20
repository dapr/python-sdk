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

from dapr.ext.workflow.execution_info import WorkflowExecutionInfo
from dapr.ext.workflow.interceptors import unwrap_payload_with_metadata, wrap_payload_with_metadata
from dapr.ext.workflow.logger import Logger, LoggerOptions
from dapr.ext.workflow.retry_policy import RetryPolicy
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_context import Workflow, WorkflowContext
from durabletask import task
from durabletask.deterministic import (  # type: ignore[F401]
    DeterministicContextMixin,
)

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class Handlers(enum.Enum):
    CALL_ACTIVITY = 'call_activity'
    CALL_CHILD_WORKFLOW = 'call_child_workflow'
    CONTINUE_AS_NEW = 'continue_as_new'


class DaprWorkflowContext(WorkflowContext, DeterministicContextMixin):
    """Workflow context wrapper with deterministic utilities and metadata helpers.

    Purpose
    -------
    - Proxy to the underlying ``durabletask.task.OrchestrationContext`` (engine fields like
      ``trace_parent``, ``orchestration_span_id``, and ``workflow_attempt`` pass through).
    - Provide SDK-level helpers for durable metadata propagation via interceptors.
    - Expose ``execution_info`` as a per-activation snapshot complementing live properties.

    Tips
    ----
    - Use ``ctx.get_metadata()/set_metadata()`` to manage outbound propagation.
    - Use ``ctx.execution_info.inbound_metadata`` to inspect what arrived on this activation.
    - Prefer engine-backed properties for tracing/attempts when available (not yet available in dapr sidecar); fall back to
      metadata only for app-specific context.
    """

    def __init__(
        self,
        ctx: task.OrchestrationContext,
        logger_options: Optional[LoggerOptions] = None,
        *,
        outbound_handlers: dict[Handlers, Any] | None = None,
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
        activity: Union[Callable[[WorkflowActivityContext, TInput], TOutput], str],
        *,
        input: TInput = None,
        retry_policy: Optional[RetryPolicy] = None,
        app_id: Optional[str] = None,
        metadata: dict[str, str] | None = None,
    ) -> task.Task[TOutput]:
        # Handle string activity names for cross-app scenarios
        if isinstance(activity, str):
            activity_name = activity
            if app_id is not None:
                self._logger.debug(
                    f'{self.instance_id}: Creating cross-app activity {activity_name} for app {app_id}'
                )
            else:
                self._logger.debug(f'{self.instance_id}: Creating activity {activity_name}')

            if retry_policy is None:
                return self.__obj.call_activity(activity=activity_name, input=input, app_id=app_id)
            return self.__obj.call_activity(
                activity=activity_name, input=input, retry_policy=retry_policy.obj, app_id=app_id
            )

        # Handle function activity objects (original behavior)
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
            return self.__obj.call_activity(activity=act, input=transformed_input, app_id=app_id)
        return self.__obj.call_activity(
            activity=act, input=transformed_input, retry_policy=retry_policy.obj, app_id=app_id
        )

    def call_child_workflow(
        self,
        workflow: Union[Workflow, str],
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
        app_id: Optional[str] = None,
        metadata: dict[str, str] | None = None,
    ) -> task.Task[TOutput]:
        # Handle string workflow names for cross-app scenarios
        if isinstance(workflow, str):
            workflow_name = workflow
            self._logger.debug(f'{self.instance_id}: Creating child workflow {workflow_name}')

            if retry_policy is None:
                return self.__obj.call_sub_orchestrator(
                    workflow_name, input=input, instance_id=instance_id, app_id=app_id
                )
            return self.__obj.call_sub_orchestrator(
                workflow_name,
                input=input,
                instance_id=instance_id,
                retry_policy=retry_policy.obj,
                app_id=app_id,
            )

        # Handle function workflow objects (original behavior)
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
                wf, input=transformed_input, instance_id=instance_id, app_id=app_id
            )
        return self.__obj.call_sub_orchestrator(
            wf,
            input=transformed_input,
            instance_id=instance_id,
            retry_policy=retry_policy.obj,
            app_id=app_id,
        )

    def wait_for_external_event(self, name: str) -> task.Task:
        self._logger.debug(f'{self.instance_id}: Waiting for external event {name}')
        return self.__obj.wait_for_external_event(name)

    def continue_as_new(
        self,
        new_input: Any,
        *,
        save_events: bool = False,
        carryover_metadata: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """
        Continue the workflow execution with new inputs and optional metadata or headers.

        This method allows restarting the workflow execution with new input parameters,
        while optionally preserving workflow events, metadata, and/or headers. It also
        integrates with workflow interceptors if configured, enabling custom modification
        of inputs and associated metadata before continuation.

        Args:
            new_input: Any new input to pass to the workflow upon continuation.
            save_events (bool): Indicates whether to preserve the event history of the
                workflow execution. Defaults to False.
            carryover_metadata bool: If True, carries
                over metadata from the current execution.
            metadata dict[str, str] | None: If a dictionary is provided, it
                will be added to the current metadata. If carryover_metadata is True,
                the contents of the dictionary will be merged with the current metadata.
        """
        self._logger.debug(f'{self.instance_id}: Continuing as new')
        # Allow workflow outbound interceptors (wired via runtime) to modify payload/metadata
        transformed_input: Any = new_input
        if Handlers.CONTINUE_AS_NEW in self._outbound_handlers and callable(
            self._outbound_handlers[Handlers.CONTINUE_AS_NEW]
        ):
            transformed_input = self._outbound_handlers[Handlers.CONTINUE_AS_NEW](
                self, new_input, self.get_metadata()
            )

        # Merge/carry metadata if requested, unwrapping any envelope produced by interceptors
        payload, base_md = unwrap_payload_with_metadata(transformed_input)
        # Start with current context metadata; then layer any interceptor-provided metadata on top
        current_md = self.get_metadata() or {}
        effective_md = (current_md | (base_md or {})) if carryover_metadata else {}
        if metadata is not None:
            effective_md = effective_md | metadata

        payload = wrap_payload_with_metadata(payload, effective_md)
        self.__obj.continue_as_new(payload, save_events=save_events)


def when_all(tasks: List[task.Task]) -> task.WhenAllTask:
    """Returns a task that completes when all of the provided tasks complete or when one of the
    tasks fail."""
    return task.when_all(tasks)


def when_any(tasks: List[task.Task]) -> task.WhenAnyTask:
    """Returns a task that completes when any of the provided tasks complete or fail."""
    return task.when_any(tasks)
