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

from collections.abc import Iterable
from typing import Any, Callable

from durabletask import task
from durabletask.aio.awaitables import (
    AwaitableBase as _BaseAwaitable,  # type: ignore[import-not-found]
)
from durabletask.aio.awaitables import (
    ExternalEventAwaitable as _DTExternalEventAwaitable,
)
from durabletask.aio.awaitables import (
    SleepAwaitable as _DTSleepAwaitable,
)
from durabletask.aio.awaitables import (
    WhenAllAwaitable as _DTWhenAllAwaitable,
)

AwaitableBase = _BaseAwaitable


class ActivityAwaitable(AwaitableBase):
    def __init__(
        self,
        ctx: Any,
        activity_fn: Callable[..., Any],
        *,
        input: Any = None,
        retry_policy: Any = None,
        metadata: dict[str, str] | None = None,
    ):
        self._ctx = ctx
        self._activity_fn = activity_fn
        self._input = input
        self._retry_policy = retry_policy
        self._metadata = metadata

    def _to_task(self) -> task.Task:
        if self._retry_policy is None:
            return self._ctx.call_activity(
                self._activity_fn, input=self._input, metadata=self._metadata
            )
        return self._ctx.call_activity(
            self._activity_fn,
            input=self._input,
            retry_policy=self._retry_policy,
            metadata=self._metadata,
        )


class SubOrchestratorAwaitable(AwaitableBase):
    def __init__(
        self,
        ctx: Any,
        workflow_fn: Callable[..., Any],
        *,
        input: Any = None,
        instance_id: str | None = None,
        retry_policy: Any = None,
        metadata: dict[str, str] | None = None,
    ):
        self._ctx = ctx
        self._workflow_fn = workflow_fn
        self._input = input
        self._instance_id = instance_id
        self._retry_policy = retry_policy
        self._metadata = metadata

    def _to_task(self) -> task.Task:
        if self._retry_policy is None:
            return self._ctx.call_child_workflow(
                self._workflow_fn,
                input=self._input,
                instance_id=self._instance_id,
                metadata=self._metadata,
            )
        return self._ctx.call_child_workflow(
            self._workflow_fn,
            input=self._input,
            instance_id=self._instance_id,
            retry_policy=self._retry_policy,
            metadata=self._metadata,
        )


class SleepAwaitable(_DTSleepAwaitable):
    pass


class ExternalEventAwaitable(_DTExternalEventAwaitable):
    pass


class WhenAllAwaitable(_DTWhenAllAwaitable):
    pass


class WhenAnyAwaitable(AwaitableBase):
    def __init__(self, tasks_like: Iterable[AwaitableBase | task.Task]):
        self._tasks_like = list(tasks_like)

    def _to_task(self) -> task.Task:
        underlying: list[task.Task] = []
        for a in self._tasks_like:
            if isinstance(a, AwaitableBase):
                underlying.append(a._to_task())  # type: ignore[attr-defined]
            elif isinstance(a, task.Task):
                underlying.append(a)
            else:
                raise TypeError('when_any expects AwaitableBase or durabletask.task.Task')
        return task.when_any(underlying)
