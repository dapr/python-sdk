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

from __future__ import annotations
from typing import Callable, TypeVar

from durabletask import task

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowActivityContext:
    """Defines properties and methods for task activity context objects."""

    def __init__(self, ctx: task.ActivityContext):
        self.__obj = ctx

    @property
    def workflow_id(self) -> str:
        """Gets the unique ID of the current workflow instance"""
        return self.__obj.orchestration_id

    @property
    def task_id(self) -> int:
        """Gets the unique ID of the current workflow task"""
        return self.__obj.task_id

    def get_inner_context(self) -> task.ActivityContext:
        return self.__obj


# Activities are simple functions that can be scheduled by workflows
Activity = Callable[..., TOutput]
