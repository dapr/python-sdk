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

import asyncio
import inspect

from dapr.ext.workflow.workflow_runtime import WorkflowRuntime


class _FakeRegistry:
    def __init__(self):
        self.activities = {}

    def add_named_activity(self, name, fn):
        self.activities[name] = fn


class _FakeWorker:
    def __init__(self, *args, **kwargs):
        self._registry = _FakeRegistry()

    def start(self):
        pass

    def stop(self):
        pass


class _FakeActivityContext:
    def __init__(self):
        self.orchestration_id = 'test-orch-id'
        self.task_id = 1


def test_activity_decorator_supports_async(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.activity(name='async_act')
    async def async_act(ctx, x: int) -> int:
        await asyncio.sleep(0)  # Simulate async work
        return x + 2

    # Ensure registered
    reg = rt._WorkflowRuntime__worker._registry
    assert 'async_act' in reg.activities

    # Verify the wrapper is async
    wrapper = reg.activities['async_act']
    assert inspect.iscoroutinefunction(wrapper), 'Async activity wrapper should be a coroutine'

    # Call the wrapper and ensure it returns a coroutine that can be awaited
    ctx = _FakeActivityContext()
    coro = wrapper(ctx, 5)
    assert inspect.iscoroutine(coro), 'Async wrapper should return a coroutine'

    # Run the coroutine and verify result
    out = asyncio.run(coro)
    assert out == 7


def test_activity_decorator_supports_sync(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.activity(name='sync_act')
    def sync_act(ctx, x: int) -> int:
        return x * 3

    # Ensure registered
    reg = rt._WorkflowRuntime__worker._registry
    assert 'sync_act' in reg.activities

    # Verify the wrapper is sync
    wrapper = reg.activities['sync_act']
    assert not inspect.iscoroutinefunction(wrapper), (
        'Sync activity wrapper should not be a coroutine'
    )

    # Call the wrapper directly (no await needed)
    ctx = _FakeActivityContext()
    out = wrapper(ctx, 4)
    assert out == 12


def test_async_and_sync_activities_coexist(monkeypatch):
    """Test that both async and sync activities can be registered in the same runtime."""
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.activity(name='sync_act')
    def sync_act(ctx, x: int) -> int:
        return x * 2

    @rt.activity(name='async_act')
    async def async_act(ctx, x: int) -> int:
        await asyncio.sleep(0)
        return x + 10

    # Ensure both registered
    reg = rt._WorkflowRuntime__worker._registry
    assert 'sync_act' in reg.activities
    assert 'async_act' in reg.activities

    # Verify correct wrapper types
    sync_wrapper = reg.activities['sync_act']
    async_wrapper = reg.activities['async_act']
    assert not inspect.iscoroutinefunction(sync_wrapper)
    assert inspect.iscoroutinefunction(async_wrapper)

    # Verify both work correctly
    ctx = _FakeActivityContext()
    sync_result = sync_wrapper(ctx, 5)
    assert sync_result == 10

    async_result = asyncio.run(async_wrapper(ctx, 5))
    assert async_result == 15
