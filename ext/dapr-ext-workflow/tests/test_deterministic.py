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

import datetime as _dt

import pytest
from dapr.ext.workflow.aio import AsyncWorkflowContext
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext

"""
Tests for deterministic helpers shared across workflow contexts.
"""


class _FakeBaseCtx:
    def __init__(self, instance_id: str, dt: _dt.datetime):
        self.instance_id = instance_id
        self.current_utc_datetime = dt


def _fixed_dt():
    return _dt.datetime(2024, 1, 1)


def test_random_string_deterministic_across_instances_async():
    base = _FakeBaseCtx('iid-1', _fixed_dt())
    a_ctx = AsyncWorkflowContext(base)
    b_ctx = AsyncWorkflowContext(base)
    a = a_ctx.random_string(16)
    b = b_ctx.random_string(16)
    assert a == b


def test_random_string_deterministic_across_context_types():
    base = _FakeBaseCtx('iid-2', _fixed_dt())
    a_ctx = AsyncWorkflowContext(base)
    s1 = a_ctx.random_string(12)

    # Minimal fake orchestration context for DaprWorkflowContext
    d_ctx = DaprWorkflowContext(base)
    s2 = d_ctx.random_string(12)
    assert s1 == s2


def test_random_string_respects_alphabet():
    base = _FakeBaseCtx('iid-3', _fixed_dt())
    ctx = AsyncWorkflowContext(base)
    s = ctx.random_string(20, alphabet='abc')
    assert set(s).issubset(set('abc'))


def test_random_string_length_and_edge_cases():
    base = _FakeBaseCtx('iid-4', _fixed_dt())
    ctx = AsyncWorkflowContext(base)

    assert ctx.random_string(0) == ''

    with pytest.raises(ValueError):
        ctx.random_string(-1)

    with pytest.raises(ValueError):
        ctx.random_string(5, alphabet='')
