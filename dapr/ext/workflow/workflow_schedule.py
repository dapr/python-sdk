# -*- coding: utf-8 -*-
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

"""Return types for the workflow schedule APIs.

These back :meth:`DaprWorkflowClient.get_workflow_schedule` and
:meth:`DaprWorkflowClient.list_workflow_schedules`, on both the sync and the
async client. All datetimes are naive UTC, the same convention as
WorkflowState.created_at.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import dapr.ext.workflow._durabletask.internal.helpers as pbh
import dapr.ext.workflow._durabletask.internal.protos as pb
from dapr.ext.workflow._durabletask.client import OrchestrationStatus
from dapr.ext.workflow._durabletask.task import FailureDetails
from dapr.ext.workflow.workflow_management import _failure_details_of
from dapr.ext.workflow.workflow_state import WorkflowStatus


def _datetime_of(message: Any, field: str) -> Optional[datetime]:
    if not message.HasField(field):
        return None
    return getattr(message, field).ToDatetime()


def _workflow_status_of(value: int) -> WorkflowStatus:
    """Maps a wire status to WorkflowStatus, as WorkflowState.runtime_status does."""
    try:
        status_name = OrchestrationStatus(value).name
    except ValueError:
        return WorkflowStatus.UNKNOWN
    return WorkflowStatus.__members__.get(status_name, WorkflowStatus.UNKNOWN)


class WorkflowScheduleState(Enum):
    """How a workflow schedule stands.

    Any state the runtime adds but this SDK version does not know maps to
    :attr:`UNKNOWN` rather than raising.
    """

    UNKNOWN = -1
    ACTIVE = pb.WORKFLOW_SCHEDULE_STATE_ACTIVE
    """Waiting for its next run."""
    COMPLETED = pb.WORKFLOW_SCHEDULE_STATE_COMPLETED
    """No runs left, because of repeats or expiration_time."""
    FAILED = pb.WORKFLOW_SCHEDULE_STATE_FAILED
    """Stopped with an error, given in WorkflowScheduleStatus.failure_message."""

    @classmethod
    def _missing_(cls, value: object) -> WorkflowScheduleState:
        return cls.UNKNOWN


@dataclass(frozen=True)
class WorkflowScheduleRun:
    """One run of a workflow schedule, read from its workflow instance.

    Only instance_id is set when the runtime cannot read the run's instance,
    for example because it was purged.

    Attributes:
        instance_id: The run's workflow instance ID.
        runtime_status: The run's status.
        created_at: When the run's instance was created.
        last_updated_at: When the run's instance last changed.
        serialized_output: The run's output, as JSON.
        failure_details: The error, if the run failed.
    """

    instance_id: str
    runtime_status: Optional[WorkflowStatus]
    created_at: Optional[datetime]
    last_updated_at: Optional[datetime]
    serialized_output: Optional[str]
    failure_details: Optional[FailureDetails]

    @classmethod
    def _from_proto(cls, run: pb.WorkflowScheduleRun) -> WorkflowScheduleRun:
        runtime_status = (
            _workflow_status_of(run.runtimeStatus) if run.HasField('runtimeStatus') else None
        )
        return cls(
            instance_id=run.instanceId,
            runtime_status=runtime_status,
            created_at=_datetime_of(run, 'createdTimestamp'),
            last_updated_at=_datetime_of(run, 'lastUpdatedTimestamp'),
            serialized_output=None if pbh.is_empty(run.output) else run.output.value,
            failure_details=_failure_details_of(run),
        )


@dataclass(frozen=True)
class WorkflowScheduleStatus:
    """How a workflow schedule stands, as reported by the runtime.

    Attributes:
        state: Whether the schedule is active, completed or failed.
        created_at: When the schedule was created.
        next_run_time: When the next run starts, unless it is triggered sooner.
            None once the schedule is not active.
        last_run_time: The time the last run was started for: its fire time,
            or when it was triggered.
        run_count: The number of runs started so far, triggered ones included.
        last_run: How the last run stands. None before the first run.
        failure_message: Why the schedule failed, when state is FAILED.
    """

    state: WorkflowScheduleState
    created_at: datetime
    next_run_time: Optional[datetime]
    last_run_time: Optional[datetime]
    run_count: int
    last_run: Optional[WorkflowScheduleRun]
    failure_message: Optional[str]

    @classmethod
    def _from_proto(cls, status: pb.WorkflowScheduleStatus) -> WorkflowScheduleStatus:
        last_run = (
            WorkflowScheduleRun._from_proto(status.lastRun) if status.HasField('lastRun') else None
        )
        return cls(
            state=WorkflowScheduleState(status.state),
            created_at=status.createdAt.ToDatetime(),
            next_run_time=_datetime_of(status, 'nextRunTime'),
            last_run_time=_datetime_of(status, 'lastRunTime'),
            run_count=status.runCount,
            last_run=last_run,
            failure_message=None
            if pbh.is_empty(status.failureMessage)
            else status.failureMessage.value,
        )


@dataclass(frozen=True)
class WorkflowSchedule:
    """A schedule that starts a workflow repeatedly, as a new instance each run.

    Each run is a detached workflow instance with the ID
    ``"<name>_<owner>_<fire time>"``, where the owner is a 6-character tag of
    the app that owns the schedule and the fire time is formatted as
    ``20060102T150405Z`` (UTC); a triggered run's ID ends in ``"_manual"``. So
    the runs of a schedule are the instances whose ID starts with
    ``"<name>_<owner>_"``.

    Attributes:
        name: The schedule's name, unique within the app.
        workflow_name: The name of the workflow each run starts.
        schedule: When runs start, in the syntax of the Dapr Jobs API.
        serialized_input: The input every run is given, as JSON.
        due_time: The time of the first run, if one was set.
        expiration_time: The time after which no run starts, if one was set.
        repeats: The number of runs after which the schedule completes, if set.
        app_id: The app that hosts the workflow, if not this one.
        app_namespace: The namespace of app_id, if not this one.
        skip_missed: Whether the times missed while the app was down start one
            run between them, rather than one run each.
        status: How the schedule stands. Always set on the schedules the runtime
            returns; typed Optional only because the wire field is.
    """

    name: str
    workflow_name: str
    schedule: str
    serialized_input: Optional[str]
    due_time: Optional[datetime]
    expiration_time: Optional[datetime]
    repeats: Optional[int]
    app_id: Optional[str]
    app_namespace: Optional[str]
    skip_missed: bool
    status: Optional[WorkflowScheduleStatus]

    @classmethod
    def _from_proto(cls, schedule: pb.WorkflowSchedule) -> WorkflowSchedule:
        status = (
            WorkflowScheduleStatus._from_proto(schedule.status)
            if schedule.HasField('status')
            else None
        )
        return cls(
            name=schedule.name,
            workflow_name=schedule.workflowName,
            schedule=schedule.schedule,
            serialized_input=None if pbh.is_empty(schedule.input) else schedule.input.value,
            due_time=_datetime_of(schedule, 'dueTime'),
            expiration_time=_datetime_of(schedule, 'expirationTime'),
            repeats=schedule.repeats if schedule.HasField('repeats') else None,
            app_id=schedule.targetAppID if schedule.HasField('targetAppID') else None,
            app_namespace=schedule.targetAppNamespace
            if schedule.HasField('targetAppNamespace')
            else None,
            skip_missed=schedule.HasField('skipMissed') and schedule.skipMissed,
            status=status,
        )


@dataclass(frozen=True)
class WorkflowSchedulePage:
    """One page of workflow schedules.

    Attributes:
        schedules: The schedules in this page. A page can hold fewer than the
            page size asked for, or none, while more remain.
        continuation_token: Pass it back unchanged as the next call's
            continuation_token to get the following page; None means this was
            the last page.
    """

    schedules: list[WorkflowSchedule]
    continuation_token: Optional[str]

    @classmethod
    def _from_proto(cls, res: pb.ListWorkflowSchedulesResponse) -> WorkflowSchedulePage:
        return cls(
            schedules=[WorkflowSchedule._from_proto(schedule) for schedule in res.schedules],
            continuation_token=res.continuationToken if res.HasField('continuationToken') else None,
        )
