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

from abc import abstractmethod
from typing import Any, Callable, List, TypeVar, Union
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

class CompositeTask(task.Task[T]):
    """A task that is composed of other tasks."""
    _tasks: List[task.Task]

    def __init__(self, tasks: List[task.Task]):
        super().__init__()
        self._tasks = tasks
        self._completed_tasks = 0
        self._failed_tasks = 0
        for task in tasks:
            task._parent = self # type: ignore
            if task.is_complete:
                self.on_child_completed(task)

    def get_tasks(self) -> List[task.Task]:
        return self._tasks

    @abstractmethod
    def on_child_completed(self, task: task.Task[T]):
        pass


class WhenAllTask(CompositeTask[List[T]]):
    """A task that completes when all of its child tasks complete."""

    def __init__(self, tasks: List[task.Task[T]]):
        super().__init__(tasks)
        self._completed_tasks = 0
        self._failed_tasks = 0

    @property
    def pending_tasks(self) -> int:
        """Returns the number of tasks that have not yet completed."""
        return len(self._tasks) - self._completed_tasks

    def on_child_completed(self, task: task.Task[T]):
        if self.is_complete:
            raise ValueError('The task has already completed.')
        self._completed_tasks += 1
        if task.is_failed and self._exception is None:
            self._exception = task.get_exception()
            self._is_complete = True
        if self._completed_tasks == len(self._tasks):
            # The order of the result MUST match the order of the tasks provided to the constructor.
            self._result = [task.get_result() for task in self._tasks]
            self._is_complete = True

    def get_completed_tasks(self) -> int:
        return self._completed_tasks


class WhenAnyTask(CompositeTask[task.Task]):
    """A task that completes when any of its child tasks complete."""

    def __init__(self, tasks: List[task.Task]):
        super().__init__(tasks)

    def on_child_completed(self, task: task.Task):
        # The first task to complete is the result of the WhenAnyTask.
        if not self.is_complete:
            self._is_complete = True
            self._result = task


def when_all(tasks: List[task.Task[T]]) -> WhenAllTask[T]:
    """Returns a task that completes when all of the provided tasks complete or when one of the tasks fail."""
    return WhenAllTask(tasks)

def when_any(tasks: List[task.Task]) -> WhenAnyTask:
    """Returns a task that completes when any of the provided tasks complete or fail."""
    return WhenAnyTask(tasks)