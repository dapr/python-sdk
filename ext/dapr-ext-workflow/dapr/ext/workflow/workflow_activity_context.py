from __future__ import annotations
from typing import Callable, TypeVar

from durabletask import task

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowActivityContext():

    __ignore__ = "class mro new init setattr getattr getattribute"

    def __init__(self, obj: task.ActivityContext):
        self._obj = obj

    def workflow_id(self) -> str:
        return self._obj.orchestration_id

    def task_id(self) -> int:
        return self._obj.task_id

    def get_inner_context(self) -> task.ActivityContext:
        return self._obj


# Activities are simple functions that can be scheduled by workflows
Activity = Callable[[WorkflowActivityContext, TInput], TOutput]
