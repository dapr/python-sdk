# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import traceback
from datetime import datetime
from typing import Optional, Union

import dapr.ext.workflow._durabletask.internal.protos as pb
from google.protobuf import timestamp_pb2, wrappers_pb2

TimerOrigin = Union[
    pb.TimerOriginCreateTimer,
    pb.TimerOriginExternalEvent,
    pb.TimerOriginActivityRetry,
    pb.TimerOriginChildWorkflowRetry,
]

_ORIGIN_FIELD: dict[type, str] = {
    pb.TimerOriginCreateTimer: 'createTimer',
    pb.TimerOriginExternalEvent: 'externalEvent',
    pb.TimerOriginActivityRetry: 'activityRetry',
    pb.TimerOriginChildWorkflowRetry: 'childWorkflowRetry',
}

# Sentinel fireAt used for "optional" TimerOriginExternalEvent timers that back an
# indefinite wait_for_external_event. The sentinel is 9999-12-31T23:59:59.999999999Z
# (nanosecond precision — cannot be represented with Python's datetime, which only
# supports microseconds, so we build the Timestamp directly).
OPTIONAL_TIMER_FIRE_AT: timestamp_pb2.Timestamp = timestamp_pb2.Timestamp(
    seconds=253402300799, nanos=999999999
)


def is_optional_timer_action(action: pb.WorkflowAction) -> bool:
    """Returns True if the action is an optional TimerOriginExternalEvent timer
    with the sentinel fireAt — i.e. created by an indefinite wait_for_external_event.

    Pre-patch histories (from prior SDK versions that didn't schedule a timer for
    indefinite waits) won't carry a matching TimerCreatedEvent; the replay logic
    uses this check to drop the optional action and shift sequence ids.
    """
    if not action.HasField('createTimer'):
        return False
    timer = action.createTimer
    if timer.WhichOneof('origin') != 'externalEvent':
        return False
    return (
        timer.fireAt.seconds == OPTIONAL_TIMER_FIRE_AT.seconds
        and timer.fireAt.nanos == OPTIONAL_TIMER_FIRE_AT.nanos
    )


def is_optional_timer_event(event: pb.HistoryEvent) -> bool:
    """Returns True if a TimerCreatedEvent is the optional TimerOriginExternalEvent
    sentinel timer."""
    if not event.HasField('timerCreated'):
        return False
    timer = event.timerCreated
    if timer.WhichOneof('origin') != 'externalEvent':
        return False
    return (
        timer.fireAt.seconds == OPTIONAL_TIMER_FIRE_AT.seconds
        and timer.fireAt.nanos == OPTIONAL_TIMER_FIRE_AT.nanos
    )


# TODO: The new_xxx_event methods are only used by test code and should be moved elsewhere


def new_workflow_started_event(timestamp: Optional[datetime] = None) -> pb.HistoryEvent:
    ts = timestamp_pb2.Timestamp()
    if timestamp is not None:
        ts.FromDatetime(timestamp)
    return pb.HistoryEvent(eventId=-1, timestamp=ts, workflowStarted=pb.WorkflowStartedEvent())


def new_execution_started_event(
    name: str, instance_id: str, encoded_input: Optional[str] = None
) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        executionStarted=pb.ExecutionStartedEvent(
            name=name,
            input=get_string_value(encoded_input),
            workflowInstance=pb.WorkflowInstance(instanceId=instance_id),
        ),
    )


def new_timer_created_event(
    timer_id: int,
    fire_at: Union[datetime, timestamp_pb2.Timestamp],
    origin: Optional[TimerOrigin] = None,
) -> pb.HistoryEvent:
    if isinstance(fire_at, timestamp_pb2.Timestamp):
        ts = fire_at
    else:
        ts = timestamp_pb2.Timestamp()
        ts.FromDatetime(fire_at)
    origin_kwargs = {_ORIGIN_FIELD[type(origin)]: origin} if origin is not None else {}
    return pb.HistoryEvent(
        eventId=timer_id,
        timestamp=timestamp_pb2.Timestamp(),
        timerCreated=pb.TimerCreatedEvent(fireAt=ts, **origin_kwargs),
    )


def new_timer_fired_event(timer_id: int, fire_at: datetime) -> pb.HistoryEvent:
    ts = timestamp_pb2.Timestamp()
    ts.FromDatetime(fire_at)
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        timerFired=pb.TimerFiredEvent(fireAt=ts, timerId=timer_id),
    )


def new_task_scheduled_event(
    event_id: int, name: str, encoded_input: Optional[str] = None
) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=event_id,
        timestamp=timestamp_pb2.Timestamp(),
        taskScheduled=pb.TaskScheduledEvent(name=name, input=get_string_value(encoded_input)),
    )


def new_task_completed_event(
    event_id: int, encoded_output: Optional[str] = None
) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        taskCompleted=pb.TaskCompletedEvent(
            taskScheduledId=event_id, result=get_string_value(encoded_output)
        ),
    )


def new_task_failed_event(event_id: int, ex: Exception) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        taskFailed=pb.TaskFailedEvent(
            taskScheduledId=event_id, failureDetails=new_failure_details(ex)
        ),
    )


def new_child_workflow_created_event(
    event_id: int, name: str, instance_id: str, encoded_input: Optional[str] = None
) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=event_id,
        timestamp=timestamp_pb2.Timestamp(),
        childWorkflowInstanceCreated=pb.ChildWorkflowInstanceCreatedEvent(
            name=name, input=get_string_value(encoded_input), instanceId=instance_id
        ),
    )


def new_child_workflow_completed_event(
    event_id: int, encoded_output: Optional[str] = None
) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        childWorkflowInstanceCompleted=pb.ChildWorkflowInstanceCompletedEvent(
            result=get_string_value(encoded_output), taskScheduledId=event_id
        ),
    )


def new_child_workflow_failed_event(event_id: int, ex: Exception) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        childWorkflowInstanceFailed=pb.ChildWorkflowInstanceFailedEvent(
            failureDetails=new_failure_details(ex), taskScheduledId=event_id
        ),
    )


def new_failure_details(ex: Exception) -> pb.TaskFailureDetails:
    return pb.TaskFailureDetails(
        errorType=type(ex).__name__,
        errorMessage=str(ex),
        stackTrace=wrappers_pb2.StringValue(value=''.join(traceback.format_tb(ex.__traceback__))),
    )


def new_event_raised_event(name: str, encoded_input: Optional[str] = None) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        eventRaised=pb.EventRaisedEvent(name=name, input=get_string_value(encoded_input)),
    )


def new_suspend_event() -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        executionSuspended=pb.ExecutionSuspendedEvent(),
    )


def new_resume_event() -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1, timestamp=timestamp_pb2.Timestamp(), executionResumed=pb.ExecutionResumedEvent()
    )


def new_terminated_event(*, encoded_output: Optional[str] = None) -> pb.HistoryEvent:
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        executionTerminated=pb.ExecutionTerminatedEvent(input=get_string_value(encoded_output)),
    )


def get_string_value(val: Optional[str]) -> Optional[wrappers_pb2.StringValue]:
    if val is None:
        return None
    else:
        return wrappers_pb2.StringValue(value=val)


def new_complete_workflow_action(
    id: int,
    status: pb.OrchestrationStatus,
    result: Optional[str] = None,
    failure_details: Optional[pb.TaskFailureDetails] = None,
    carryover_events: Optional[list[pb.HistoryEvent]] = None,
    router: Optional[pb.TaskRouter] = None,
) -> pb.WorkflowAction:
    completeWorkflowAction = pb.CompleteWorkflowAction(
        workflowStatus=status,
        result=get_string_value(result),
        failureDetails=failure_details,
        carryoverEvents=carryover_events,
    )

    return pb.WorkflowAction(
        id=id,
        completeWorkflow=completeWorkflowAction,
        router=router,
    )


def new_workflow_version_not_available_action(
    id: int,
) -> pb.WorkflowAction:
    return pb.WorkflowAction(
        id=id,
        workflowVersionNotAvailable=pb.WorkflowVersionNotAvailableAction(),
    )


def new_create_timer_action(
    id: int,
    fire_at: Union[datetime, timestamp_pb2.Timestamp],
    origin: Optional[TimerOrigin] = None,
) -> pb.WorkflowAction:
    if isinstance(fire_at, timestamp_pb2.Timestamp):
        timestamp = fire_at
    else:
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(fire_at)
    origin_kwargs = {_ORIGIN_FIELD[type(origin)]: origin} if origin is not None else {}
    return pb.WorkflowAction(
        id=id, createTimer=pb.CreateTimerAction(fireAt=timestamp, **origin_kwargs)
    )


def new_schedule_task_action(
    id: int,
    name: str,
    encoded_input: Optional[str],
    router: Optional[pb.TaskRouter] = None,
    task_execution_id: str = '',
) -> pb.WorkflowAction:
    return pb.WorkflowAction(
        id=id,
        scheduleTask=pb.ScheduleTaskAction(
            name=name,
            input=get_string_value(encoded_input),
            router=router,
            taskExecutionId=task_execution_id,
        ),
        router=router,
    )


def new_timestamp(dt: datetime) -> timestamp_pb2.Timestamp:
    ts = timestamp_pb2.Timestamp()
    ts.FromDatetime(dt)
    return ts


def new_create_child_workflow_action(
    id: int,
    name: str,
    instance_id: Optional[str],
    encoded_input: Optional[str],
    router: Optional[pb.TaskRouter] = None,
) -> pb.WorkflowAction:
    return pb.WorkflowAction(
        id=id,
        createChildWorkflow=pb.CreateChildWorkflowAction(
            name=name,
            instanceId=instance_id,
            input=get_string_value(encoded_input),
            router=router,
        ),
        router=router,
    )


def is_empty(v: wrappers_pb2.StringValue):
    return v is None or v.value == ''


def get_orchestration_status_str(status: pb.OrchestrationStatus):
    try:
        const_name = pb.OrchestrationStatus.Name(status)
        if const_name.startswith('ORCHESTRATION_STATUS_'):
            return const_name[len('ORCHESTRATION_STATUS_') :]
    except Exception:
        return 'UNKNOWN'
