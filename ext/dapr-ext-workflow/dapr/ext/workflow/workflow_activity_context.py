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

from dapr.ext.workflow.execution_info import ActivityExecutionInfo

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowActivityContext:
    """Wrapper for ``durabletask.task.ActivityContext`` with metadata helpers.

    Purpose
    -------
    - Provide pass-throughs for engine fields (``trace_parent``, ``trace_state``,
      and parent ``workflow_span_id`` when available).
    - Surface ``execution_info``: a per-activation snapshot that includes the
      ``inbound_metadata`` actually received for this activity.
    - Offer ``get_metadata()/set_metadata()`` for SDK-level durable metadata management.
    """

    def __init__(self, ctx: task.ActivityContext):
        self.__obj = ctx
        self._metadata: dict[str, str] | None = None

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

    @property
    def execution_info(self) -> ActivityExecutionInfo | None:
        return getattr(self, '_execution_info', None)

    def _set_execution_info(self, info: ActivityExecutionInfo) -> None:
        self._execution_info = info

    # Metadata accessors (SDK-level; set by runtime inbound if available)
    def set_metadata(self, metadata: dict[str, str] | None) -> None:
        self._metadata = dict(metadata) if metadata else None

    def get_metadata(self) -> dict[str, str] | None:
        return dict(self._metadata) if self._metadata else None


# Activities are simple functions that can be scheduled by workflows
Activity = Callable[..., TOutput]
