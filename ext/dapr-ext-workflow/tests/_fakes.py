"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class FakeOrchestrationContext:
    def __init__(
        self,
        *,
        instance_id: str = 'wf-1',
        current_utc_datetime: datetime | None = None,
        is_replaying: bool = False,
        workflow_name: str = 'wf',
        trace_parent: str | None = None,
        trace_state: str | None = None,
        orchestration_span_id: str | None = None,
        workflow_attempt: int | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.current_utc_datetime = (
            current_utc_datetime if current_utc_datetime else datetime(2025, 1, 1)
        )
        self.is_replaying = is_replaying
        self.workflow_name = workflow_name
        self.trace_parent = trace_parent
        self.trace_state = trace_state
        self.orchestration_span_id = orchestration_span_id
        self.workflow_attempt = workflow_attempt


class FakeActivityContext:
    def __init__(
        self,
        *,
        orchestration_id: str = 'wf-1',
        task_id: int = 1,
        attempt: int | None = None,
        trace_parent: str | None = None,
        trace_state: str | None = None,
        workflow_span_id: str | None = None,
    ) -> None:
        self.orchestration_id = orchestration_id
        self.task_id = task_id
        self.trace_parent = trace_parent
        self.trace_state = trace_state
        self.workflow_span_id = workflow_span_id


def make_orch_ctx(**overrides: Any) -> FakeOrchestrationContext:
    return FakeOrchestrationContext(**overrides)


def make_act_ctx(**overrides: Any) -> FakeActivityContext:
    return FakeActivityContext(**overrides)
