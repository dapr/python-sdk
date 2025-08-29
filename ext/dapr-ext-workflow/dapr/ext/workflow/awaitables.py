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
See the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, List, Optional

from durabletask import task

from .async_driver import DaprOperation
import importlib

"""
Awaitable helpers for async workflows. Each awaitable yields a DaprOperation wrapping
an underlying Durable Task task.
"""


class AwaitableBase:
    def _to_dapr_task(self) -> task.Task:
        raise NotImplementedError

    def __await__(self):  # type: ignore[override]
        result = yield DaprOperation(self._to_dapr_task())
        return result


class ActivityAwaitable(AwaitableBase):
    def __init__(
        self,
        ctx: Any,
        activity_fn: Callable[..., Any],
        *,
        input: Any = None,
        retry_policy: Any = None,
    ):
        self._ctx = ctx
        self._activity_fn = activity_fn
        self._input = input
        self._retry_policy = retry_policy

    def _to_dapr_task(self) -> task.Task:
        if self._retry_policy is None:
            return self._ctx.call_activity(self._activity_fn, input=self._input)
        return self._ctx.call_activity(
            self._activity_fn, input=self._input, retry_policy=self._retry_policy
        )


class SubOrchestratorAwaitable(AwaitableBase):
    def __init__(
        self,
        ctx: Any,
        workflow_fn: Callable[..., Any],
        *,
        input: Any = None,
        instance_id: Optional[str] = None,
        retry_policy: Any = None,
    ):
        self._ctx = ctx
        self._workflow_fn = workflow_fn
        self._input = input
        self._instance_id = instance_id
        self._retry_policy = retry_policy

    def _to_dapr_task(self) -> task.Task:
        if self._retry_policy is None:
            return self._ctx.call_child_workflow(
                self._workflow_fn, input=self._input, instance_id=self._instance_id
            )
        return self._ctx.call_child_workflow(
            self._workflow_fn,
            input=self._input,
            instance_id=self._instance_id,
            retry_policy=self._retry_policy,
        )


class SleepAwaitable(AwaitableBase):
    def __init__(self, ctx: Any, duration: float | timedelta | datetime):
        self._ctx = ctx
        self._duration = duration

    def _to_dapr_task(self) -> task.Task:
        deadline: datetime | timedelta
        deadline = self._duration
        return self._ctx.create_timer(deadline)


class ExternalEventAwaitable(AwaitableBase):
    def __init__(self, ctx: Any, name: str):
        self._ctx = ctx
        self._name = name

    def _to_dapr_task(self) -> task.Task:
        return self._ctx.wait_for_external_event(self._name)


class WhenAllAwaitable(AwaitableBase):
    def __init__(self, tasks_like: Iterable[AwaitableBase | task.Task]):
        self._tasks_like = list(tasks_like)

    def _to_dapr_task(self) -> task.Task:
        underlying: List[task.Task] = []
        for a in self._tasks_like:
            if isinstance(a, AwaitableBase):
                underlying.append(a._to_dapr_task())  # type: ignore[attr-defined]
            elif isinstance(a, task.Task):
                underlying.append(a)
            else:
                raise TypeError('when_all expects AwaitableBase or durabletask.task.Task')
        return task.when_all(underlying)


class WhenAnyAwaitable(AwaitableBase):
    def __init__(self, tasks_like: Iterable[AwaitableBase | task.Task]):
        self._tasks_like = list(tasks_like)

    def _to_dapr_task(self) -> task.Task:
        underlying: List[task.Task] = []
        for a in self._tasks_like:
            if isinstance(a, AwaitableBase):
                underlying.append(a._to_dapr_task())  # type: ignore[attr-defined]
            elif isinstance(a, task.Task):
                underlying.append(a)
            else:
                raise TypeError('when_any expects AwaitableBase or durabletask.task.Task')
        return task.when_any(underlying)


def _resolve_callable(module_name: str, qualname: str) -> Callable[..., Any]:
    mod = importlib.import_module(module_name)
    obj: Any = mod
    for part in qualname.split('.'):
        obj = getattr(obj, part)
    if not callable(obj):
        raise TypeError(f'resolved object {module_name}.{qualname} is not callable')
    return obj


def _gather_catcher(ctx: Any, desc: dict[str, Any]):  # generator orchestrator
    try:
        kind = desc.get('kind')
        if kind == 'activity':
            fn = _resolve_callable(desc['module'], desc['qualname'])
            rp = desc.get('retry_policy')
            if rp is None:
                result = yield ctx.call_activity(fn, input=desc.get('input'))
            else:
                result = yield ctx.call_activity(fn, input=desc.get('input'), retry_policy=rp)
            return result
        if kind == 'subwf':
            fn = _resolve_callable(desc['module'], desc['qualname'])
            rp = desc.get('retry_policy')
            if rp is None:
                result = yield ctx.call_child_workflow(
                    fn, input=desc.get('input'), instance_id=desc.get('instance_id')
                )
            else:
                result = yield ctx.call_child_workflow(
                    fn,
                    input=desc.get('input'),
                    instance_id=desc.get('instance_id'),
                    retry_policy=rp,
                )
            return result
        raise TypeError('unsupported gather child kind')
    except Exception as e:  # swallow and return exception descriptor
        return {'__exception__': True, 'type': type(e).__name__, 'message': str(e)}


class GatherReturnExceptionsAwaitable(AwaitableBase):
    def __init__(self, ctx: Any, children: Iterable[AwaitableBase]):
        self._ctx = ctx
        self._children = list(children)

    def _to_dapr_task(self) -> task.Task:
        wrapped: List[task.Task] = []
        for child in self._children:
            if isinstance(child, ActivityAwaitable):
                fn = child._activity_fn  # type: ignore[attr-defined]
                desc = {
                    'kind': 'activity',
                    'module': getattr(fn, '__module__', ''),
                    'qualname': getattr(fn, '__qualname__', ''),
                    'input': child._input,  # type: ignore[attr-defined]
                    'retry_policy': getattr(child, '_retry_policy', None),
                }
            elif isinstance(child, SubOrchestratorAwaitable):
                fn = child._workflow_fn  # type: ignore[attr-defined]
                desc = {
                    'kind': 'subwf',
                    'module': getattr(fn, '__module__', ''),
                    'qualname': getattr(fn, '__qualname__', ''),
                    'input': child._input,  # type: ignore[attr-defined]
                    'instance_id': getattr(child, '_instance_id', None),
                    'retry_policy': getattr(child, '_retry_policy', None),
                }
            else:
                raise TypeError(
                    'gather(return_exceptions=True) supports only activity or sub-workflow awaitables'
                )
            wrapped.append(self._ctx.call_child_workflow(_gather_catcher, input=desc))
        return task.when_all(wrapped)
