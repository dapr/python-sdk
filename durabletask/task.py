# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# See https://peps.python.org/pep-0563/
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Callable, Generator, Generic, Optional, TypeVar, Union

import durabletask.internal.helpers as pbh
import durabletask.internal.protos as pb

T = TypeVar("T")
TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class OrchestrationContext(ABC):
    @property
    @abstractmethod
    def instance_id(self) -> str:
        """Get the ID of the current orchestration instance.

        The instance ID is generated and fixed when the orchestrator function
        is scheduled. It can be either auto-generated, in which case it is
        formatted as a UUID, or it can be user-specified with any format.

        Returns
        -------
        str
            The ID of the current orchestration instance.
        """
        pass

    @property
    @abstractmethod
    def current_utc_datetime(self) -> datetime:
        """Get the current date/time as UTC.

        This date/time value is derived from the orchestration history. It
        always returns the same value at specific points in the orchestrator
        function code, making it deterministic and safe for replay.

        Returns
        -------
        datetime
            The current timestamp in a way that is safe for use by orchestrator functions
        """
        pass

    @property
    @abstractmethod
    def is_replaying(self) -> bool:
        """Get the value indicating whether the orchestrator is replaying from history.

        This property is useful when there is logic that needs to run only when
        the orchestrator function is _not_ replaying. For example, certain
        types of application logging may become too noisy when duplicated as
        part of orchestrator function replay. The orchestrator code could check
        to see whether the function is being replayed and then issue the log
        statements when this value is `false`.

        Returns
        -------
        bool
            Value indicating whether the orchestrator function is currently replaying.
        """
        pass

    @abstractmethod
    def set_custom_status(self, custom_status: str) -> None:
        """Set the orchestration instance's custom status.

        Parameters
        ----------
        custom_status: str
            A custom status string to set.
        """
        pass

    @abstractmethod
    def create_timer(self, fire_at: Union[datetime, timedelta]) -> Task:
        """Create a Timer Task to fire after at the specified deadline.

        Parameters
        ----------
        fire_at: datetime.datetime | datetime.timedelta
            The time for the timer to trigger or a time delta from now.

        Returns
        -------
        Task
            A Durable Timer Task that schedules the timer to wake up the orchestrator
        """
        pass

    @abstractmethod
    def call_activity(
        self,
        activity: Union[Activity[TInput, TOutput], str],
        *,
        input: Optional[TInput] = None,
        retry_policy: Optional[RetryPolicy] = None,
        app_id: Optional[str] = None,
    ) -> Task[TOutput]:
        """Schedule an activity for execution.

        Parameters
        ----------
        activity: Union[Activity[TInput, TOutput], str]
            A reference to the activity function to call.
        input: Optional[TInput]
            The JSON-serializable input (or None) to pass to the activity.
        retry_policy: Optional[RetryPolicy]
            The retry policy to use for this activity call.
        app_id: Optional[str]
            The app ID that will execute the activity. If not specified, the activity will be executed by the same app as the orchestrator.

        Returns
        -------
        Task
            A Durable Task that completes when the called activity function completes or fails.
        """
        pass

    @abstractmethod
    def call_sub_orchestrator(
        self,
        orchestrator: Orchestrator[TInput, TOutput],
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
        app_id: Optional[str] = None,
    ) -> Task[TOutput]:
        """Schedule sub-orchestrator function for execution.

        Parameters
        ----------
        orchestrator: Orchestrator[TInput, TOutput]
            A reference to the orchestrator function to call.
        input: Optional[TInput]
            The optional JSON-serializable input to pass to the orchestrator function.
        instance_id: Optional[str]
            A unique ID to use for the sub-orchestration instance. If not specified, a
            random UUID will be used.
        retry_policy: Optional[RetryPolicy]
            The retry policy to use for this sub-orchestrator call.
        app_id: Optional[str]
            The app ID that will execute the sub-orchestrator. If not specified, the sub-orchestrator will be executed by the same app as the orchestrator.

        Returns
        -------
        Task
            A Durable Task that completes when the called sub-orchestrator completes or fails.
        """
        pass

    # TOOD: Add a timeout parameter, which allows the task to be canceled if the event is
    # not received within the specified timeout. This requires support for task cancellation.
    @abstractmethod
    def wait_for_external_event(self, name: str) -> Task:
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
            A flag indicating whether to add any unprocessed external events in the new orchestration history.
        """
        pass

    @abstractmethod
    def is_patched(self, patch_name: str) -> bool:
        """Check if the given patch name can be applied to the orchestration.

        Parameters
        ----------
        patch_name : str
            The name of the patch to check.

        Returns
        -------
        bool
            True if the given patch name can be applied to the orchestration, False otherwise.
        """
        pass


class FailureDetails:
    def __init__(self, message: str, error_type: str, stack_trace: Optional[str]):
        self._message = message
        self._error_type = error_type
        self._stack_trace = stack_trace

    @property
    def message(self) -> str:
        return self._message

    @property
    def error_type(self) -> str:
        return self._error_type

    @property
    def stack_trace(self) -> Optional[str]:
        return self._stack_trace


class TaskFailedError(Exception):
    """Exception type for all orchestration task failures."""

    def __init__(self, message: str, details: pb.TaskFailureDetails):
        super().__init__(message)
        self._details = FailureDetails(
            details.errorMessage,
            details.errorType,
            details.stackTrace.value if not pbh.is_empty(details.stackTrace) else None,
        )

    @property
    def details(self) -> FailureDetails:
        return self._details


class NonDeterminismError(Exception):
    pass


class OrchestrationStateError(Exception):
    pass


class NonRetryableError(Exception):
    """Exception indicating the operation should not be retried.

    If an activity or sub-orchestration raises this exception, retry logic will be
    bypassed and the failure will be returned immediately to the orchestrator.
    """

    pass


def is_error_non_retryable(error_type: str, policy: RetryPolicy) -> bool:
    """Checks whether an error type is non-retryable."""
    is_non_retryable = False
    if error_type == "NonRetryableError":
        is_non_retryable = True
    elif (
        policy.non_retryable_error_types is not None
        and error_type in policy.non_retryable_error_types
    ):
        is_non_retryable = True
    return is_non_retryable


class Task(ABC, Generic[T]):
    """Abstract base class for asynchronous tasks in a durable orchestration."""

    _result: T
    _exception: Optional[TaskFailedError]
    _parent: Optional[CompositeTask[T]]

    def __init__(self) -> None:
        super().__init__()
        self._is_complete = False
        self._exception = None
        self._parent = None

    @property
    def is_complete(self) -> bool:
        """Returns True if the task has completed, False otherwise."""
        return self._is_complete

    @property
    def is_failed(self) -> bool:
        """Returns True if the task has failed, False otherwise."""
        return self._exception is not None

    def get_result(self) -> T:
        """Returns the result of the task."""
        if not self._is_complete:
            raise ValueError("The task has not completed.")
        elif self._exception is not None:
            raise self._exception
        return self._result

    def get_exception(self) -> TaskFailedError:
        """Returns the exception that caused the task to fail."""
        if self._exception is None:
            raise ValueError("The task has not failed.")
        return self._exception


class CompositeTask(Task[T]):
    """A task that is composed of other tasks."""

    _tasks: list[Task]

    def __init__(self, tasks: list[Task]):
        super().__init__()
        self._tasks = tasks
        self._completed_tasks = 0
        self._failed_tasks = 0
        for task in tasks:
            task._parent = self
            if task.is_complete:
                self.on_child_completed(task)

    def get_tasks(self) -> list[Task]:
        return self._tasks

    @abstractmethod
    def on_child_completed(self, task: Task[T]):
        pass


class WhenAllTask(CompositeTask[list[T]]):
    """A task that completes when all of its child tasks complete."""

    def __init__(self, tasks: list[Task[T]]):
        super().__init__(tasks)
        self._completed_tasks = 0
        self._failed_tasks = 0
        # If there are no child tasks, this composite should complete immediately
        if len(self._tasks) == 0:
            self._result = []  # type: ignore[assignment]
            self._is_complete = True

    @property
    def pending_tasks(self) -> int:
        """Returns the number of tasks that have not yet completed."""
        return len(self._tasks) - self._completed_tasks

    def on_child_completed(self, task: Task[T]):
        if self.is_complete:
            raise ValueError("The task has already completed.")
        self._completed_tasks += 1
        if task.is_failed and self._exception is None:
            self._exception = task.get_exception()
            self._is_complete = True
        if self._completed_tasks == len(self._tasks):
            # The order of the result MUST match the order of the tasks provided to the constructor.
            self._result = [task.get_result() for task in self._tasks]
            self._is_complete = True
            if self._parent is not None:
                self._parent.on_child_completed(self)

    def get_completed_tasks(self) -> int:
        return self._completed_tasks


class CompletableTask(Task[T]):
    def __init__(self):
        super().__init__()
        self._retryable_parent = None

    def complete(self, result: T):
        if self._is_complete:
            raise ValueError("The task has already completed.")
        self._result = result
        self._is_complete = True
        if self._parent is not None:
            self._parent.on_child_completed(self)

    def fail(self, message: str, details: pb.TaskFailureDetails):
        if self._is_complete:
            raise ValueError("The task has already completed.")
        self._exception = TaskFailedError(message, details)
        self._is_complete = True
        if self._parent is not None:
            self._parent.on_child_completed(self)


class RetryableTask(CompletableTask[T]):
    """A task that can be retried according to a retry policy."""

    def __init__(
        self,
        retry_policy: RetryPolicy,
        start_time: datetime,
        is_sub_orch: bool,
        task_name: str,
        encoded_input: Optional[str] = None,
        task_execution_id: str = "",
        instance_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._retry_policy = retry_policy
        self._attempt_count = 1
        self._start_time = start_time
        self._is_sub_orch = is_sub_orch
        self._task_name = task_name
        self._encoded_input = encoded_input
        self._task_execution_id = task_execution_id
        self._instance_id = instance_id
        self._app_id = app_id

    def increment_attempt_count(self) -> None:
        self._attempt_count += 1

    def compute_next_delay(self) -> Optional[timedelta]:
        if self._attempt_count >= self._retry_policy.max_number_of_attempts:
            return None

        retry_expiration: datetime = datetime.max
        if (
            self._retry_policy.retry_timeout is not None
            and self._retry_policy.retry_timeout != datetime.max
        ):
            retry_expiration = self._start_time + self._retry_policy.retry_timeout

        if self._retry_policy.backoff_coefficient is None:
            backoff_coefficient = 1.0
        else:
            backoff_coefficient = self._retry_policy.backoff_coefficient

        if datetime.utcnow() < retry_expiration:
            next_delay_f = (
                math.pow(backoff_coefficient, self._attempt_count - 1)
                * self._retry_policy.first_retry_interval.total_seconds()
            )

            if self._retry_policy.max_retry_interval is not None:
                next_delay_f = min(
                    next_delay_f, self._retry_policy.max_retry_interval.total_seconds()
                )
            return timedelta(seconds=next_delay_f)

        return None


class TimerTask(CompletableTask[T]):
    def __init__(self) -> None:
        super().__init__()

    def set_retryable_parent(self, retryable_task: RetryableTask):
        self._retryable_parent = retryable_task


class WhenAnyTask(CompositeTask[Task]):
    """A task that completes when any of its child tasks complete."""

    def __init__(self, tasks: list[Task]):
        super().__init__(tasks)
        # If there are no child tasks, complete immediately with an empty result
        if len(self._tasks) == 0:
            self._result = []  # type: ignore[assignment]
            self._is_complete = True

    def on_child_completed(self, task: Task):
        # The first task to complete is the result of the WhenAnyTask.
        if not self.is_complete:
            self._is_complete = True
            self._result = task
            if self._parent is not None:
                self._parent.on_child_completed(self)


def when_all(tasks: list[Task[T]]) -> WhenAllTask[T]:
    """Returns a task that completes when all of the provided tasks complete or when one of the tasks fail."""
    return WhenAllTask(tasks)


def when_any(tasks: list[Task]) -> WhenAnyTask:
    """Returns a task that completes when any of the provided tasks complete or fail."""
    return WhenAnyTask(tasks)


class ActivityContext:
    def __init__(self, orchestration_id: str, task_id: int, task_execution_id: str = ""):
        self._orchestration_id = orchestration_id
        self._task_id = task_id
        self._task_execution_id = task_execution_id

    @property
    def orchestration_id(self) -> str:
        """Get the ID of the orchestration instance that scheduled this activity.

        Returns
        -------
        str
            The ID of the current orchestration instance.
        """
        return self._orchestration_id

    @property
    def task_id(self) -> int:
        """Get the task ID associated with this activity invocation.

        The task ID is an auto-incrementing integer that is unique within
        the scope of the orchestration instance. It can be used to distinguish
        between multiple activity invocations that are part of the same
        orchestration instance.

        Returns
        -------
        str
            The ID of the current orchestration instance.
        """
        return self._task_id

    @property
    def task_execution_id(self) -> str:
        """Get the task execution ID associated with this activity invocation.

        The task execution ID is a UUID that is stable across retry attempts
        of the same activity call. It can be used for idempotency and
        deduplication when an activity may be retried.

        Returns
        -------
        str
            The task execution ID for this activity invocation.
        """
        return self._task_execution_id


# Orchestrators are generators that yield tasks and receive/return any type
Orchestrator = Callable[[OrchestrationContext, TInput], Union[Generator[Task, Any, Any], TOutput]]

# Activities are simple functions that can be scheduled by orchestrators
Activity = Callable[[ActivityContext, TInput], TOutput]


class RetryPolicy:
    """Represents the retry policy for an orchestration or activity function."""

    def __init__(
        self,
        *,
        first_retry_interval: timedelta,
        max_number_of_attempts: int,
        backoff_coefficient: Optional[float] = 1.0,
        max_retry_interval: Optional[timedelta] = None,
        retry_timeout: Optional[timedelta] = None,
        non_retryable_error_types: Optional[list[Union[str, type]]] = None,
    ):
        """Creates a new RetryPolicy instance.

        Parameters
        ----------
        first_retry_interval : timedelta
            The retry interval to use for the first retry attempt.
        max_number_of_attempts : int
            The maximum number of retry attempts.
        backoff_coefficient : Optional[float]
            The backoff coefficient to use for calculating the next retry interval.
        max_retry_interval : Optional[timedelta]
            The maximum retry interval to use for any retry attempt.
        retry_timeout : Optional[timedelta]
            The maximum amount of time to spend retrying the operation.
        non_retryable_error_types : Optional[list[Union[str, type]]]
            A list of exception type names or classes that should not be retried.
            If a failure's error type matches any of these, the task fails immediately.
            The built-in NonRetryableError is always treated as non-retryable regardless
            of this setting.
        """
        # validate inputs
        if first_retry_interval < timedelta(seconds=0):
            raise ValueError("first_retry_interval must be >= 0")
        if max_number_of_attempts < 1:
            raise ValueError("max_number_of_attempts must be >= 1")
        if backoff_coefficient is not None and backoff_coefficient < 1:
            raise ValueError("backoff_coefficient must be >= 1")
        if max_retry_interval is not None and max_retry_interval < timedelta(seconds=0):
            raise ValueError("max_retry_interval must be >= 0")
        if retry_timeout is not None and retry_timeout < timedelta(seconds=0):
            raise ValueError("retry_timeout must be >= 0")

        self._first_retry_interval = first_retry_interval
        self._max_number_of_attempts = max_number_of_attempts
        self._backoff_coefficient = backoff_coefficient
        self._max_retry_interval = max_retry_interval
        self._retry_timeout = retry_timeout
        # Normalize non-retryable error type names to a set of strings
        names: Optional[set[str]] = None
        if non_retryable_error_types:
            names = set[str]()
            for t in non_retryable_error_types:
                if isinstance(t, str) and t:
                    names.add(t)
                elif isinstance(t, type):
                    names.add(t.__name__)
        self._non_retryable_error_types = names

    @property
    def first_retry_interval(self) -> timedelta:
        """The retry interval to use for the first retry attempt."""
        return self._first_retry_interval

    @property
    def max_number_of_attempts(self) -> int:
        """The maximum number of retry attempts."""
        return self._max_number_of_attempts

    @property
    def backoff_coefficient(self) -> Optional[float]:
        """The backoff coefficient to use for calculating the next retry interval."""
        return self._backoff_coefficient

    @property
    def max_retry_interval(self) -> Optional[timedelta]:
        """The maximum retry interval to use for any retry attempt."""
        return self._max_retry_interval

    @property
    def retry_timeout(self) -> Optional[timedelta]:
        """The maximum amount of time to spend retrying the operation."""
        return self._retry_timeout

    @property
    def non_retryable_error_types(self) -> Optional[set[str]]:
        """Set of error type names that should not be retried.

        Comparison is performed against the errorType string provided by the
        backend (typically the exception class name).
        """
        return self._non_retryable_error_types


def get_name(fn: Callable) -> str:
    """Returns the name of the provided function"""
    name = fn.__name__
    if name == "<lambda>":
        raise ValueError(
            "Cannot infer a name from a lambda function. Please provide a name explicitly."
        )

    return name
