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

"""Timer-related helpers for the durabletask workflow SDK.

This module keeps all timer / TimerOrigin concerns in one place, separate from
the generic action/event helpers in ``helpers.py``.
"""

from datetime import datetime
from typing import Optional, Union

import dapr.ext.workflow._durabletask.internal.protos as pb
from google.protobuf import timestamp_pb2

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

# Sentinel fireAt used for "optional" TimerOriginExternalEvent timers that back
# an indefinite wait_for_external_event. The sentinel is
# 9999-12-31T23:59:59.999999999Z (nanosecond precision — Python's ``datetime``
# is only microsecond-precision, so we build the Timestamp directly).
OPTIONAL_TIMER_FIRE_AT: timestamp_pb2.Timestamp = timestamp_pb2.Timestamp(
    seconds=253402300799, nanos=999999999
)


def _origin_kwargs(origin: Optional[TimerOrigin]) -> dict:
    """Build keyword args that set the correct origin oneof field on a
    ``CreateTimerAction`` / ``TimerCreatedEvent`` proto."""
    if origin is None:
        return {}
    return {_ORIGIN_FIELD[type(origin)]: origin}


def _to_timestamp(
    fire_at: Union[datetime, timestamp_pb2.Timestamp],
) -> timestamp_pb2.Timestamp:
    """Normalize a ``fire_at`` argument to a protobuf ``Timestamp``."""
    if isinstance(fire_at, timestamp_pb2.Timestamp):
        return fire_at
    ts = timestamp_pb2.Timestamp()
    ts.FromDatetime(fire_at)
    return ts


def _fire_at_matches_sentinel(ts: timestamp_pb2.Timestamp) -> bool:
    """Return True iff ``ts`` exactly matches :data:`OPTIONAL_TIMER_FIRE_AT`.

    Both ``seconds`` and ``nanos`` are proto3 scalars that are always present
    (default 0 when unset), so unconditional field access is safe.
    """
    return ts.seconds == OPTIONAL_TIMER_FIRE_AT.seconds and ts.nanos == OPTIONAL_TIMER_FIRE_AT.nanos


def is_optional_timer_action(action: pb.WorkflowAction) -> bool:
    """Returns True if the action is an optional TimerOriginExternalEvent timer
    with the sentinel fireAt — i.e. created by an indefinite wait_for_external_event.

    Pre-patch histories (from prior SDK versions that didn't schedule a timer
    for indefinite waits) won't carry a matching TimerCreatedEvent; the replay
    logic uses this check to drop the optional action and shift sequence ids.
    """
    if not action.HasField('createTimer'):
        return False
    timer = action.createTimer
    if timer.WhichOneof('origin') != 'externalEvent':
        return False
    return _fire_at_matches_sentinel(timer.fireAt)


def is_optional_timer_event(event: pb.HistoryEvent) -> bool:
    """Returns True if a TimerCreatedEvent is the optional sentinel timer.

    For replay compatibility, treat a timerCreated event with the sentinel
    fireAt as optional even if the proto3 ``origin`` oneof is unset (e.g. when
    reading histories emitted by older sidecars that didn't populate it). When
    ``origin`` *is* populated, it must match TimerOriginExternalEvent.
    """
    if not event.HasField('timerCreated'):
        return False
    timer = event.timerCreated
    if not _fire_at_matches_sentinel(timer.fireAt):
        return False
    origin = timer.WhichOneof('origin')
    return origin in (None, 'externalEvent')


def new_create_timer_action(
    timer_id: int,
    fire_at: Union[datetime, timestamp_pb2.Timestamp],
    origin: Optional[TimerOrigin] = None,
) -> pb.WorkflowAction:
    ts = _to_timestamp(fire_at)
    return pb.WorkflowAction(
        id=timer_id,
        createTimer=pb.CreateTimerAction(fireAt=ts, **_origin_kwargs(origin)),
    )


def new_timer_created_event(
    timer_id: int,
    fire_at: Union[datetime, timestamp_pb2.Timestamp],
    origin: Optional[TimerOrigin] = None,
) -> pb.HistoryEvent:
    ts = _to_timestamp(fire_at)
    return pb.HistoryEvent(
        eventId=timer_id,
        timestamp=timestamp_pb2.Timestamp(),
        timerCreated=pb.TimerCreatedEvent(fireAt=ts, **_origin_kwargs(origin)),
    )


def new_timer_fired_event(
    timer_id: int,
    fire_at: Union[datetime, timestamp_pb2.Timestamp],
) -> pb.HistoryEvent:
    ts = _to_timestamp(fire_at)
    return pb.HistoryEvent(
        eventId=-1,
        timestamp=timestamp_pb2.Timestamp(),
        timerFired=pb.TimerFiredEvent(fireAt=ts, timerId=timer_id),
    )
