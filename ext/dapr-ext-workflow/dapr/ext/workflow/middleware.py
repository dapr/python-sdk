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

from typing import Any, Awaitable, Protocol, runtime_checkable, Callable


@runtime_checkable
class RuntimeMiddleware(Protocol):
    """Protocol for workflow/activity middleware hooks.

    Implementers may optionally define any subset of these methods.
    Methods may return an awaitable, which will be run to completion by the runtime.
    """

    # Workflow lifecycle
    def on_workflow_start(self, ctx: Any, input: Any) -> Awaitable[None] | None: ...
    def on_workflow_yield(self, ctx: Any, yielded: Any) -> Awaitable[None] | None: ...
    def on_workflow_resume(self, ctx: Any, resumed_value: Any) -> Awaitable[None] | None: ...
    def on_workflow_complete(self, ctx: Any, result: Any) -> Awaitable[None] | None: ...
    def on_workflow_error(self, ctx: Any, error: BaseException) -> Awaitable[None] | None: ...

    # Activity lifecycle
    def on_activity_start(self, ctx: Any, input: Any) -> Awaitable[None] | None: ...
    def on_activity_complete(self, ctx: Any, result: Any) -> Awaitable[None] | None: ...
    def on_activity_error(self, ctx: Any, error: BaseException) -> Awaitable[None] | None: ...

    # Outbound workflow hooks (deterministic, sync-only expected)
    def on_call_activity(
        self,
        ctx: Any,
        activity: Callable[..., Any] | str,
        input: Any,
        retry_policy: Any | None,
    ) -> Any: ...

    def on_call_child_workflow(
        self,
        ctx: Any,
        workflow: Callable[..., Any] | str,
        input: Any,
    ) -> Any: ...


class MiddlewareOrder:
    """Used to order middleware execution; lower = earlier on start/yield/resume.

    Complete/error hooks run in reverse order (stack semantics).
    """

    DEFAULT = 0


class MiddlewarePolicy:
    """Error handling policy for middleware hook failures."""

    CONTINUE_ON_ERROR = "continue"
    RAISE_ON_ERROR = "raise"




