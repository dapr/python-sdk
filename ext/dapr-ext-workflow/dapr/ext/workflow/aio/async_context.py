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
from typing import Any, Awaitable, Callable, Sequence

from durabletask import task
from durabletask.deterministic import (  # type: ignore[F401]
    DeterministicContextMixin,
)

from .awaitables import (
    ActivityAwaitable,
    ExternalEventAwaitable,
    SleepAwaitable,
    SubOrchestratorAwaitable,
    WhenAllAwaitable,
    WhenAnyAwaitable,
)

"""
Async workflow context that exposes deterministic awaitables for activities, timers,
external events, and concurrency, along with deterministic utilities.
"""


class AsyncWorkflowContext(DeterministicContextMixin):
    def __init__(self, base_ctx: task.OrchestrationContext):
        self._base_ctx = base_ctx
        # Initialize metadata from base context if available
        base_metadata = None
        if hasattr(base_ctx, 'get_metadata') and callable(base_ctx.get_metadata):
            base_metadata = base_ctx.get_metadata()
        self._metadata: dict[str, str] | None = base_metadata

    # Core workflow metadata parity with sync context
    @property
    def instance_id(self) -> str:
        return self._base_ctx.instance_id

    @property
    def current_utc_datetime(self) -> datetime:
        return self._base_ctx.current_utc_datetime

    # Activities & Sub-orchestrations
    def call_activity(
        self,
        activity_fn: Callable[..., Any],
        *,
        input: Any = None,
        retry_policy: Any = None,
        metadata: dict[str, str] | None = None,
    ) -> Awaitable[Any]:
        return ActivityAwaitable(
            self._base_ctx, activity_fn, input=input, retry_policy=retry_policy, metadata=metadata
        )

    def call_child_workflow(
        self,
        workflow_fn: Callable[..., Any],
        *,
        input: Any = None,
        instance_id: str | None = None,
        retry_policy: Any = None,
        metadata: dict[str, str] | None = None,
    ) -> Awaitable[Any]:
        return SubOrchestratorAwaitable(
            self._base_ctx,
            workflow_fn,
            input=input,
            instance_id=instance_id,
            retry_policy=retry_policy,
            metadata=metadata,
        )

    @property
    def is_replaying(self) -> bool:
        return self._base_ctx.is_replaying

    # Timers & Events
    def create_timer(self, fire_at: int | float | timedelta | datetime) -> Awaitable[None]:
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

    # Deterministic utilities are provided by mixin (now, random, uuid4, new_guid)

    @property
    def is_suspended(self) -> bool:
        # Placeholder; will be wired when Durable Task exposes this state in context
        return self._base_ctx.is_suspended

    # Pass-throughs for completeness
    def set_custom_status(self, custom_status: str) -> None:
        if hasattr(self._base_ctx, 'set_custom_status'):
            self._base_ctx.set_custom_status(custom_status)

    def continue_as_new(
        self,
        new_input: Any,
        *,
        save_events: bool = False,
        carryover_metadata: bool | dict[str, str] = False,
        carryover_headers: bool | dict[str, str] | None = None,
    ) -> None:
        effective_carryover = (
            carryover_headers if carryover_headers is not None else carryover_metadata
        )
        # Try extended signature; fall back to minimal for older fakes/contexts
        try:
            self._base_ctx.continue_as_new(
                new_input, save_events=save_events, carryover_metadata=effective_carryover
            )
        except TypeError:
            self._base_ctx.continue_as_new(new_input, save_events=save_events)

    # Metadata parity
    def set_metadata(self, metadata: dict[str, str] | None) -> None:
        self._metadata = dict(metadata) if metadata else None
        # Sync with base context if it supports metadata
        if hasattr(self._base_ctx, 'set_metadata') and callable(self._base_ctx.set_metadata):
            self._base_ctx.set_metadata(self._metadata)

    def get_metadata(self) -> dict[str, str] | None:
        return dict(self._metadata) if self._metadata else None

    # Header aliases (ergonomic alias for users familiar with Temporal terminology)
    def set_headers(self, headers: dict[str, str] | None) -> None:
        self.set_metadata(headers)

    def get_headers(self) -> dict[str, str] | None:
        return self.get_metadata()

    # Execution info parity - use our own managed _execution_info attribute
    @property
    def execution_info(self):  # type: ignore[override]
        return getattr(self._base_ctx, '_execution_info', None)


__all__ = [
    'AsyncWorkflowContext',
]
