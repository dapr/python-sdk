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

import pytest
from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        import datetime

        self.current_utc_datetime = datetime.datetime(2024, 1, 1)
        self.instance_id = 'iid-act-retry'

    def call_activity(self, activity, *, input=None, retry_policy=None, metadata=None, app_id=None):
        return FakeTask('activity')

    def create_timer(self, fire_at):
        return FakeTask('timer')


async def wf(ctx: AsyncWorkflowContext):
    # One activity that ultimately fails after retries
    await ctx.call_activity(lambda: None, retry_policy={'dummy': True})
    return 'not-reached'


def test_activity_retry_final_failure_raises():
    fake = FakeCtx()
    runner = CoroutineOrchestratorRunner(wf)
    gen = runner.to_generator(AsyncWorkflowContext(fake), None)
    # Prime
    next(gen)
    # Simulate final failure after retry policy exhausts
    with pytest.raises(RuntimeError, match='activity failed'):
        gen.throw(RuntimeError('activity failed'))
