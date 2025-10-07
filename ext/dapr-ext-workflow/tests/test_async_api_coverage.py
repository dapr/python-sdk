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

from datetime import datetime

from dapr.ext.workflow.aio import AsyncWorkflowContext


class FakeCtx:
    def __init__(self):
        self.current_utc_datetime = datetime(2024, 1, 1)
        self.instance_id = 'iid-cov'
        self._status = None

    def set_custom_status(self, status):
        self._status = status

    def continue_as_new(self, new_input, *, save_events=False):
        self._continued = (new_input, save_events)

    # methods used by awaitables
    def call_activity(self, activity, *, input=None, retry_policy=None):
        class _T:
            pass

        return _T()

    def call_child_workflow(self, workflow, *, input=None, instance_id=None, retry_policy=None):
        class _T:
            pass

        return _T()

    def create_timer(self, fire_at):
        class _T:
            pass

        return _T()

    def wait_for_external_event(self, name: str):
        class _T:
            pass

        return _T()


def test_async_context_exposes_required_methods():
    base = FakeCtx()
    ctx = AsyncWorkflowContext(base)

    # basic deterministic utils existence
    assert isinstance(ctx.now(), datetime)
    _ = ctx.random()
    _ = ctx.uuid4()

    # pass-throughs
    ctx.set_custom_status('ok')
    assert base._status == 'ok'
    ctx.continue_as_new({'foo': 1}, save_events=True)
    assert getattr(base, '_continued', None) == ({'foo': 1}, True)

    # awaitable constructors do not raise
    ctx.call_activity(lambda: None, input={'x': 1})
    ctx.call_child_workflow(lambda: None)
    ctx.sleep(1.0)
    ctx.wait_for_external_event('go')
    ctx.when_all([])
    ctx.when_any([])
