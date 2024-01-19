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
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Callable, Generator, Optional, TypeVar, Union

from durabletask import task

from dapr.ext.workflow.workflow_activity_context import Activity

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowContext(ABC):
    """Context object used by workflow implementations to perform actions such as scheduling
    activities, durable timers, waiting for external events, and for getting basic information
    about the current workflow instance.
    """

    @property
    @abstractmethod
    def instance_id(self) -> str:
        """Get the ID of the current workflow instance.

        The instance ID is generated and fixed when the workflow
        is scheduled. It can be either auto-generated, in which case it is
        formatted as a UUID, or it can be user-specified with any format.

        Returns
        -------
        str
            The ID of the current workflow.
        """
        pass

    @property
    @abstractmethod
    def current_utc_datetime(self) -> datetime:
        """Get the current date/time as UTC.

        This date/time value is derived from the workflow history. It
        always returns the same value at specific points in the workflow
        function code, making it deterministic and safe for replay.

        Returns
        -------
        datetime
            The current timestamp in a way that is safe for use by workflow functions
        """
        pass

    @property
    @abstractmethod
    def is_replaying(self) -> bool:
        """Get the value indicating whether the workflow is replaying from history.

        This property is useful when there is logic that needs to run only when
        the workflow is _not_ replaying. For example, certain
        types of application logging may become too noisy when duplicated as
        part of workflow replay. The workflow code could check
        to see whether the function is being replayed and then issue the log
        statements when this value is `false`.

        Returns
        -------
        bool
            Value indicating whether the workflow is currently replaying.
        """
        pass

    @abstractmethod
    def create_timer(self, fire_at: Union[datetime, timedelta]) -> task.Task:
        """Create a Timer Task to fire after at the specified deadline.

        Parameters
        ----------
        fire_at: datetime.datetime | datetime.timedelta
            The time for the timer to trigger. Can be specified as a `datetime` or a `timedelta`.

        Returns
        -------
        Task
            A Durable Timer Task that schedules the timer to wake up the orchestrator
        """
        pass

    @abstractmethod
    def call_activity(
        self, activity: Activity[TOutput], *, input: Optional[TInput] = None
    ) -> task.Task[TOutput]:
        """Schedule an activity for execution.

        Parameters
        ----------
        activity: Activity[TInput, TOutput]
            A reference to the activity function to call.
        input: TInput | None
            The JSON-serializable input (or None) to pass to the activity.
        return_type: task.Task[TOutput]
            The JSON-serializable output type to expect from the activity result.

        Returns
        -------
        Task
            A Durable Task that completes when the called activity function completes or fails.
        """
        pass

    @abstractmethod
    def call_child_workflow(
        self,
        orchestrator: Workflow[TOutput],
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
    ) -> task.Task[TOutput]:
        """Schedule child-workflow function for execution.

        Parameters
        ----------
        orchestrator: Orchestrator[TInput, TOutput]
            A reference to the orchestrator function to call.
        input: TInput
            The optional JSON-serializable input to pass to the orchestrator function.
        instance_id: str
            A unique ID to use for the sub-orchestration instance. If not specified, a
            random UUID will be used.

        Returns
        -------
        Task
            A Durable Task that completes when the called child-workflow completes or fails.
        """
        pass

    @abstractmethod
    def wait_for_external_event(self, name: str) -> task.Task:
        """Wait asynchronously for an event to be raised with the name `name`.

        Parameters
        ----------
        name : str
            The event name of the event that the task is waiting for.

        Returns
        -------
        Task[TOutput]
            A Durable Task that completes when the event is received.
        """
        pass

    @abstractmethod
    def continue_as_new(self, new_input: Any, *, save_events: bool = False) -> None:
        """Continue the orchestration execution as a new instance.

        Parameters
        ----------
        new_input : Any
            The new input to use for the new orchestration instance.
        save_events : bool
            A flag indicating whether to add any unprocessed external events in the new
            orchestration history.
        """
        pass


# Workflows are generators that yield tasks and receive/return any type
Workflow = Callable[..., Union[Generator[task.Task, Any, Any], TOutput]]
