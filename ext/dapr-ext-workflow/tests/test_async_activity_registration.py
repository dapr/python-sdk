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


def test_activity_decorator_supports_async(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.activity(name='async_act')
    async def async_act(ctx, x: int) -> int:
        return x + 2

    # Ensure registered
    reg = rt._WorkflowRuntime__worker._registry
    assert 'async_act' in reg.activities

    # Call the wrapper and ensure it runs the coroutine to completion
    wrapper = reg.activities['async_act']

    class _Ctx:
        pass

    out = wrapper(_Ctx(), 5)
    assert out == 7
