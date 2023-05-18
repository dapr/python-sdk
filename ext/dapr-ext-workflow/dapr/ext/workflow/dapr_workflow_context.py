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

from typing import Any, Callable, TypeVar, Union
from durabletask import task
from datetime import datetime
from dapr.ext.workflow.workflow_context import WorkflowContext, Workflow

from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class DaprWorkflowContext(WorkflowContext):
    """DaprWorkflowContext that provides proxy access to internal OrchestrationContext instance."""

    def __init__(self, ctx: task.OrchestrationContext):
        self.__obj = ctx

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

    def create_timer(self, fire_at: datetime) -> task.Task:
        return self.__obj.create_timer(fire_at)

    def call_activity(self, activity: Callable[[WorkflowActivityContext, TInput], TOutput], *,
                      input: TInput = None) -> task.Task[TOutput]:
        return self.__obj.call_activity(activity=activity.__name__, input=input)

    def call_child_workflow(self, workflow: Workflow, *,
                            input: Union[TInput, None],
                            instance_id: Union[str, None]) -> task.Task[TOutput]:
        def wf(ctx: task.OrchestrationContext, inp: TInput):
            daprWfContext = DaprWorkflowContext(ctx)
            return workflow(daprWfContext, inp)
        return self.__obj.call_sub_orchestrator(wf, input=input, instance_id=instance_id)

    def wait_for_external_event(self, name: str) -> task.Task:
        return self.__obj.wait_for_external_event(name)

    def continue_as_new(self, new_input: Any, *, save_events: bool = False) -> None:
        self.__obj.continue_as_new(new_input, save_events=save_events)
