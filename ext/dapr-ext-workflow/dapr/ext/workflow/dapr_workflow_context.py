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

from typing import Any, Callable, List, Optional, TypeVar, Union
from datetime import datetime, timedelta

from durabletask import task

from dapr.ext.workflow.workflow_context import WorkflowContext, Workflow
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.logger import LoggerOptions, Logger
from dapr.ext.workflow.retry_policy import RetryPolicy

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class DaprWorkflowContext(WorkflowContext):
    """DaprWorkflowContext that provides proxy access to internal OrchestrationContext instance."""

    def __init__(
        self, ctx: task.OrchestrationContext, logger_options: Optional[LoggerOptions] = None
    ):
        self.__obj = ctx
        self._logger = Logger('DaprWorkflowContext', logger_options)

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

    def create_timer(self, fire_at: Union[datetime, timedelta]) -> task.Task:
        self._logger.debug(f'{self.instance_id}: Creating timer to fire at {fire_at} time')
        return self.__obj.create_timer(fire_at)

    def call_activity(
        self,
        activity: Callable[[WorkflowActivityContext, TInput], TOutput],
        *,
        input: TInput = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> task.Task[TOutput]:
        self._logger.debug(f'{self.instance_id}: Creating activity {activity.__name__}')
        if hasattr(activity, '_dapr_alternate_name'):
            act = activity.__dict__['_dapr_alternate_name']
        else:
            # this case should ideally never happen
            act = activity.__name__
        if retry_policy is None:
            return self.__obj.call_activity(activity=act, input=input)
        return self.__obj.call_activity(activity=act, input=input, retry_policy=retry_policy.obj)

    def call_child_workflow(
        self,
        workflow: Workflow,
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> task.Task[TOutput]:
        self._logger.debug(f'{self.instance_id}: Creating child workflow {workflow.__name__}')

        def wf(ctx: task.OrchestrationContext, inp: TInput):
            daprWfContext = DaprWorkflowContext(ctx, self._logger.get_options())
            return workflow(daprWfContext, inp)

        # copy workflow name so durabletask.worker can find the orchestrator in its registry

        if hasattr(workflow, '_dapr_alternate_name'):
            wf.__name__ = workflow.__dict__['_dapr_alternate_name']
        else:
            # this case should ideally never happen
            wf.__name__ = workflow.__name__
        if retry_policy is None:
            return self.__obj.call_sub_orchestrator(wf, input=input, instance_id=instance_id)
        return self.__obj.call_sub_orchestrator(
            wf, input=input, instance_id=instance_id, retry_policy=retry_policy.obj
        )

    def wait_for_external_event(self, name: str) -> task.Task:
        self._logger.debug(f'{self.instance_id}: Waiting for external event {name}')
        return self.__obj.wait_for_external_event(name)

    def continue_as_new(self, new_input: Any, *, save_events: bool = False) -> None:
        self._logger.debug(f'{self.instance_id}: Continuing as new')
        self.__obj.continue_as_new(new_input, save_events=save_events)


def when_all(tasks: List[task.Task[T]]) -> task.WhenAllTask[T]:
    """Returns a task that completes when all of the provided tasks complete or when one of the
    tasks fail."""
    return task.when_all(tasks)


def when_any(tasks: List[task.Task]) -> task.WhenAnyTask:
    """Returns a task that completes when any of the provided tasks complete or fail."""
    return task.when_any(tasks)
