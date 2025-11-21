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

from dapr.ext.workflow.aio import AsyncWorkflowContext
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime


class _FakeRegistry:
    def __init__(self):
        self.orchestrators = {}

    def add_named_orchestrator(self, name, fn):
        self.orchestrators[name] = fn


class _FakeWorker:
    def __init__(self, *args, **kwargs):
        self._registry = _FakeRegistry()

    def start(self):
        pass

    def stop(self):
        pass


def test_workflow_decorator_detects_async_and_registers(monkeypatch):
    import durabletask.worker as worker_mod

    monkeypatch.setattr(worker_mod, 'TaskHubGrpcWorker', _FakeWorker)

    rt = WorkflowRuntime()

    @rt.workflow(name='async_wf')
    async def async_wf(ctx: AsyncWorkflowContext, x: int) -> int:
        # no awaits to keep simple
        return x + 1

    # ensure it was placed into registry
    reg = rt._WorkflowRuntime__worker._registry
    assert 'async_wf' in reg.orchestrators
