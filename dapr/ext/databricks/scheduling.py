"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Retry-safe "ensure scheduled" logic — the primary recovery property this
extension provides. See ``dapr/ext/databricks/AGENTS.md`` for the full
delivery-semantics writeup this implements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import grpc

from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient

# Dapr's workflow "start instance" call rejects an instance ID that is
# already in use with an HTTP 409 / gRPC ALREADY_EXISTS-shaped error (see the
# Dapr Workflow API reference: "A workflow with the given instance ID already
# exists and is not yet reusable"). Match on the status code first; fall back
# to the message text since this SDK's own client already relies on message
# matching elsewhere (DaprWorkflowClient.get_workflow_state, for "no such
# instance exists") rather than assuming every backend/transport surfaces the
# same status code for this condition.
_DUPLICATE_INSTANCE_MESSAGE_MARKER = 'already exists'


@dataclass(frozen=True)
class ScheduleOutcome:
    """Result of ensuring a single workflow instance is durably scheduled."""

    instance_id: str
    newly_scheduled: bool


def is_duplicate_instance_error(error: grpc.RpcError) -> bool:
    """Reports whether ``error`` represents a duplicate-instance-ID conflict.

    Args:
        error: The gRPC error raised by ``schedule_new_workflow``.

    Returns:
        True if this error means "an instance with this ID already exists"
        rather than a genuine transport/auth/validation failure.
    """
    if error.code() == grpc.StatusCode.ALREADY_EXISTS:
        return True
    details = error.details() or ''
    return _DUPLICATE_INSTANCE_MESSAGE_MARKER in details.lower()


def ensure_workflow_scheduled(
    client: DaprWorkflowClient,
    workflow: str,
    instance_id: str,
    payload: Any,
) -> ScheduleOutcome:
    """Schedules ``workflow`` at ``instance_id`` unless it is already durably present.

    This is a check-then-act sequence, not a transaction — Dapr Workflow has
    no compare-and-swap "schedule if absent" primitive — so it relies on
    ``instance_id`` being deterministic for the same logical record and on
    Dapr rejecting a second ``schedule_new_workflow`` for an ID that is
    already in use:

    1. ``get_workflow_state`` — if the instance already exists (in any
       status), the record was already handled by a prior attempt; treat it
       as durably accepted and do nothing further.
    2. Otherwise, call ``schedule_new_workflow``. If Dapr reports the ID
       already exists (``is_duplicate_instance_error``), a concurrent caller
       won the race between step 1 and step 2; treat it the same as a normal
       existing-instance discovery. Any other error (unavailable, timeout,
       auth failure, throttling, malformed input, invalid workflow name)
       propagates so the caller can fail the micro-batch.

    A failure of ``schedule_new_workflow`` itself (e.g. a network timeout
    *after* Dapr already durably accepted the instance) also propagates here
    — this function cannot distinguish that from a genuine failure on this
    attempt. Recovery happens on the next Lakeflow retry of the same record,
    whose ``get_workflow_state`` call in step 1 will find the instance Dapr
    already accepted.

    Args:
        client: A connected ``DaprWorkflowClient``.
        workflow: Registered workflow name to schedule.
        instance_id: Deterministic instance ID for this record.
        payload: JSON-serializable workflow input.

    Returns:
        A ``ScheduleOutcome`` recording whether this call newly scheduled the
        instance or found it already durably present.

    Raises:
        grpc.RpcError: Any non-duplicate-instance scheduling failure.
    """
    existing_state = client.get_workflow_state(instance_id, fetch_payloads=False)
    if existing_state is not None:
        return ScheduleOutcome(instance_id=instance_id, newly_scheduled=False)

    try:
        client.schedule_new_workflow(workflow, input=payload, instance_id=instance_id)
    except grpc.RpcError as error:
        if is_duplicate_instance_error(error):
            return ScheduleOutcome(instance_id=instance_id, newly_scheduled=False)
        raise

    return ScheduleOutcome(instance_id=instance_id, newly_scheduled=True)
