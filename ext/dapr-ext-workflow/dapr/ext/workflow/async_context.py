# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional, Sequence, Union

from .awaitables import (
    ActivityAwaitable,
    ExternalEventAwaitable,
    SleepAwaitable,
    SubOrchestratorAwaitable,
    WhenAllAwaitable,
    WhenAnyAwaitable,
)
from .deterministic import deterministic_random, deterministic_uuid4

"""
Async workflow context that exposes deterministic awaitables for activities, timers,
external events, and concurrency, along with deterministic utilities.
"""


class AsyncWorkflowContext:
    def __init__(self, base_ctx: any):
        self._base_ctx = base_ctx

    # Activities & Sub-orchestrations
    def call_activity(
        self, activity_fn: Callable[..., Any], *, input: Any = None, retry_policy: Any = None
    ) -> Awaitable[Any]:
        return ActivityAwaitable(
            self._base_ctx, activity_fn, input=input, retry_policy=retry_policy
        )

    def call_child_workflow(
        self,
        workflow_fn: Callable[..., Any],
        *,
        input: Any = None,
        instance_id: Optional[str] = None,
        retry_policy: Any = None,
    ) -> Awaitable[Any]:
        return SubOrchestratorAwaitable(
            self._base_ctx,
            workflow_fn,
            input=input,
            instance_id=instance_id,
            retry_policy=retry_policy,
        )


    # Timers & Events
    def create_timer(self, fire_at: Union[float, timedelta, datetime]) -> Awaitable[None]:
        # If float provided, interpret as seconds
        if isinstance(fire_at, (int, float)):
            fire_at = timedelta(seconds=float(fire_at))
        return SleepAwaitable(self._base_ctx, fire_at)

    def wait_for_external_event(self, name: str) -> Awaitable[Any]:
        return ExternalEventAwaitable(self._base_ctx, name)

    # Concurrency
    def when_all(self, awaitables: Sequence[Awaitable[Any]]) -> Awaitable[list[Any]]:
        return WhenAllAwaitable(awaitables)

    def when_any(self, awaitables: Sequence[Awaitable[Any]]) -> Awaitable[Any]:
        return WhenAnyAwaitable(awaitables)

    # Deterministic utilities
    def now(self) -> datetime:
        return self._base_ctx.current_utc_datetime

    def random(self):  # returns PRNG; implement deterministic seeding in later milestone
        return deterministic_random(self._base_ctx.instance_id, self._base_ctx.current_utc_datetime)

    def uuid4(self):
        rnd = self.random()
        return deterministic_uuid4(rnd)

    @property
    def is_suspended(self) -> bool:
        # Placeholder; will be wired when Durable Task exposes this state in context
        return getattr(self._base_ctx, 'is_suspended', False)

    # Internal helpers
    def _seed(self) -> int:
        # Deprecated: use deterministic_random instead
        return 0

    # Pass-throughs for completeness
    def set_custom_status(self, custom_status: str) -> None:
        if hasattr(self._base_ctx, 'set_custom_status'):
            self._base_ctx.set_custom_status(custom_status)

    def continue_as_new(self, new_input: Any, *, save_events: bool = False) -> None:
        if hasattr(self._base_ctx, 'continue_as_new'):
            self._base_ctx.continue_as_new(new_input, save_events=save_events)
