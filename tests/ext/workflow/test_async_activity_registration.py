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

"""Unit tests for sync/async activity registration and the resulting wrappers.

These tests exercise the helpers in workflow_runtime that decide whether an activity
runs in a thread pool (sync) or as a coroutine on the event loop (async). The
WorkflowRuntime is constructed against a fake registry so we don't need a sidecar.
"""

import asyncio
import functools
import inspect
import unittest
from unittest import mock

from pydantic import BaseModel

from dapr.ext.workflow._durabletask.internal.shared import is_async_callable
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime


class OrderInput(BaseModel):
    order_id: str
    amount: float


class FakeRegistry:
    def __init__(self):
        self.activities: dict[str, object] = {}

    def add_named_activity(self, name: str, fn) -> None:
        self.activities[name] = fn


class _AsyncActivityRegistrationTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._registry_patch = mock.patch(
            'dapr.ext.workflow._durabletask.worker._Registry', return_value=FakeRegistry()
        )
        self._registry_patch.start()
        self.runtime = WorkflowRuntime()
        # Reach into the runtime to grab its registry for assertions.
        self.registry: FakeRegistry = self.runtime._WorkflowRuntime__worker._registry

    def tearDown(self) -> None:
        # Tear down the worker's ThreadPoolExecutor so each test doesn't leak threads/fds.
        # The runtime never started, so ``shutdown()`` -> ``stop()`` early-returns;
        # shut the manager down directly to actually close the executor.
        worker = self.runtime._WorkflowRuntime__worker
        self.runtime.shutdown()
        worker._async_worker_manager.shutdown()
        self._registry_patch.stop()


class AsyncActivityRegistrationTest(_AsyncActivityRegistrationTestBase):
    def test_async_activity_registers_coroutine_wrapper(self) -> None:
        async def my_async_activity(ctx: WorkflowActivityContext, payload: str) -> str:
            return payload.upper()

        self.runtime.register_activity(my_async_activity)

        wrapper = self.registry.activities['my_async_activity']
        self.assertTrue(inspect.iscoroutinefunction(wrapper))

    def test_sync_activity_registers_plain_wrapper(self) -> None:
        def my_sync_activity(ctx: WorkflowActivityContext, payload: str) -> str:
            return payload.upper()

        self.runtime.register_activity(my_sync_activity)

        wrapper = self.registry.activities['my_sync_activity']
        self.assertFalse(inspect.iscoroutinefunction(wrapper))
        self.assertTrue(callable(wrapper))

    def test_async_wrapper_awaits_user_function(self) -> None:
        recorded: list[tuple[WorkflowActivityContext, str]] = []

        async def my_async_activity(ctx: WorkflowActivityContext, payload: str) -> str:
            await asyncio.sleep(0)
            recorded.append((ctx, payload))
            return payload.upper()

        self.runtime.register_activity(my_async_activity)
        wrapper = self.registry.activities['my_async_activity']

        fake_ctx = mock.MagicMock(spec=['task_id'])
        fake_ctx.task_id = 7
        result = asyncio.run(wrapper(fake_ctx, 'hello'))

        self.assertEqual(result, 'HELLO')
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0][1], 'hello')
        self.assertIsInstance(recorded[0][0], WorkflowActivityContext)

    def test_sync_wrapper_calls_user_function(self) -> None:
        recorded: list[tuple[WorkflowActivityContext, str]] = []

        def my_sync_activity(ctx: WorkflowActivityContext, payload: str) -> str:
            recorded.append((ctx, payload))
            return payload.upper()

        self.runtime.register_activity(my_sync_activity)
        wrapper = self.registry.activities['my_sync_activity']

        fake_ctx = mock.MagicMock(spec=['task_id'])
        fake_ctx.task_id = 3
        result = wrapper(fake_ctx, 'world')

        self.assertEqual(result, 'WORLD')
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0][1], 'world')
        self.assertIsInstance(recorded[0][0], WorkflowActivityContext)

    def test_async_wrapper_coerces_input_to_declared_model(self) -> None:
        seen: list[OrderInput] = []

        async def place_order(ctx: WorkflowActivityContext, order: OrderInput) -> str:
            seen.append(order)
            return order.order_id

        self.runtime.register_activity(place_order)
        wrapper = self.registry.activities['place_order']

        fake_ctx = mock.MagicMock(spec=['task_id'])
        fake_ctx.task_id = 99
        raw_input = {'order_id': 'abc-1', 'amount': 9.5}
        result = asyncio.run(wrapper(fake_ctx, raw_input))

        self.assertEqual(result, 'abc-1')
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], OrderInput)
        self.assertEqual(seen[0].amount, 9.5)

    def test_async_wrapper_propagates_exceptions(self) -> None:
        async def failing(ctx: WorkflowActivityContext, payload: str) -> str:
            raise RuntimeError('boom')

        self.runtime.register_activity(failing)
        wrapper = self.registry.activities['failing']

        fake_ctx = mock.MagicMock(spec=['task_id'])
        fake_ctx.task_id = 1
        with self.assertRaises(RuntimeError) as caught:
            asyncio.run(wrapper(fake_ctx, 'x'))
        self.assertEqual(str(caught.exception), 'boom')

    def test_async_wrapper_supports_no_input_parameter(self) -> None:
        async def heartbeat(ctx: WorkflowActivityContext) -> str:
            return 'ok'

        self.runtime.register_activity(heartbeat)
        wrapper = self.registry.activities['heartbeat']

        fake_ctx = mock.MagicMock(spec=['task_id'])
        fake_ctx.task_id = 0
        result = asyncio.run(wrapper(fake_ctx, None))
        self.assertEqual(result, 'ok')


class IsAsyncCallableTest(unittest.TestCase):
    """Pin the contract of ``is_async_callable`` against decorator shapes that a bare
    ``inspect.iscoroutinefunction`` would miss. These are the patterns the fix for finding
    #5 was meant to address. Without coverage, a future refactor can silently regress
    async-activity routing for any of them.
    """

    def test_plain_async_function_is_async(self) -> None:
        async def fn() -> None: ...

        self.assertTrue(is_async_callable(fn))

    def test_plain_sync_function_is_not_async(self) -> None:
        def fn() -> None: ...

        self.assertFalse(is_async_callable(fn))

    def test_functools_partial_of_async_is_async(self) -> None:
        async def fn(prefix: str, payload: str) -> str:
            return prefix + payload

        partial_fn = functools.partial(fn, 'hello-')
        self.assertTrue(is_async_callable(partial_fn))

    def test_functools_partial_of_sync_is_not_async(self) -> None:
        def fn(prefix: str, payload: str) -> str:
            return prefix + payload

        partial_fn = functools.partial(fn, 'hello-')
        self.assertFalse(is_async_callable(partial_fn))

    def test_wraps_chain_over_async_is_async(self) -> None:
        """A sync decorator that uses @functools.wraps exposes the inner via __wrapped__."""

        async def inner(ctx: object, inp: object) -> None: ...

        @functools.wraps(inner)
        def outer(ctx: object, inp: object) -> object:
            return inner(ctx, inp)

        self.assertTrue(is_async_callable(outer))

    def test_nested_partial_and_wraps_chain_is_async(self) -> None:
        """partial(@wraps over async). Exercises both unwrap stages in order."""

        async def inner(prefix: str, payload: str) -> str:
            return prefix + payload

        @functools.wraps(inner)
        def wrapped(prefix: str, payload: str) -> str:
            return inner(prefix, payload)

        partial_wrapped = functools.partial(wrapped, 'hi-')
        self.assertTrue(is_async_callable(partial_wrapped))

    def test_callable_class_instance_with_async_call_is_async(self) -> None:
        class AsyncCallable:
            async def __call__(self, ctx: object, inp: object) -> str:
                return 'ok'

        self.assertTrue(is_async_callable(AsyncCallable()))

    def test_callable_class_instance_with_sync_call_is_not_async(self) -> None:
        class SyncCallable:
            def __call__(self, ctx: object, inp: object) -> str:
                return 'ok'

        self.assertFalse(is_async_callable(SyncCallable()))

    def test_cyclic_wrapped_chain_does_not_crash(self) -> None:
        """A self-referential ``__wrapped__`` makes ``inspect.unwrap`` raise; detection must
        fall back to the outermost callable instead of propagating the error."""

        async def async_cyclic() -> None: ...

        async_cyclic.__wrapped__ = async_cyclic  # type: ignore[attr-defined]

        def sync_cyclic() -> None: ...

        sync_cyclic.__wrapped__ = sync_cyclic  # type: ignore[attr-defined]

        self.assertTrue(is_async_callable(async_cyclic))
        self.assertFalse(is_async_callable(sync_cyclic))

    def test_non_callable_input_is_not_async(self) -> None:
        """The worker passes ``None`` for an unregistered activity and relies on a False
        result to route to the sync handler."""
        self.assertFalse(is_async_callable(None))
        self.assertFalse(is_async_callable(42))


class AsyncAndSyncCoexistTest(_AsyncActivityRegistrationTestBase):
    def test_runtime_registers_mixed_sync_and_async_activities(self) -> None:
        async def async_activity(ctx: WorkflowActivityContext, payload: int) -> int:
            return payload + 1

        def sync_activity(ctx: WorkflowActivityContext, payload: int) -> int:
            return payload * 2

        self.runtime.register_activity(async_activity)
        self.runtime.register_activity(sync_activity)

        async_wrapper = self.registry.activities['async_activity']
        sync_wrapper = self.registry.activities['sync_activity']

        self.assertTrue(inspect.iscoroutinefunction(async_wrapper))
        self.assertFalse(inspect.iscoroutinefunction(sync_wrapper))


if __name__ == '__main__':
    unittest.main()
