# -*- coding: utf-8 -*-
import types
from datetime import datetime, timedelta, timezone
import pytest

from dapr.ext.workflow.async_context import AsyncWorkflowContext


class DummyBaseCtx:
    def __init__(self):
        self.instance_id = "abc-123"
        # freeze a deterministic timestamp
        self.current_utc_datetime = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.is_replaying = False
        self._custom_status = None
        self._continued = None

    def set_custom_status(self, s: str):
        self._custom_status = s

    def continue_as_new(self, new_input, *, save_events: bool = False):
        self._continued = (new_input, save_events)


def test_parity_properties_and_now():
    ctx = AsyncWorkflowContext(DummyBaseCtx())
    assert ctx.instance_id == "abc-123"
    assert ctx.current_utc_datetime == datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    # now() should mirror current_utc_datetime
    assert ctx.now() == ctx.current_utc_datetime


def test_timer_accepts_float_and_timedelta():
    base = DummyBaseCtx()
    ctx = AsyncWorkflowContext(base)

    # Float should be interpreted as seconds and produce a SleepAwaitable
    aw1 = ctx.create_timer(1.5)
    # Timedelta should pass through
    aw2 = ctx.create_timer(timedelta(seconds=2))

    # We only assert types by duck-typing public attribute presence to avoid importing internal classes in tests
    assert hasattr(aw1, "_ctx") and hasattr(aw1, "__await__")
    assert hasattr(aw2, "_ctx") and hasattr(aw2, "__await__")


def test_wait_for_external_event_and_concurrency_factories():
    ctx = AsyncWorkflowContext(DummyBaseCtx())

    evt = ctx.wait_for_external_event("go")
    assert hasattr(evt, "__await__")

    # when_all/when_any/gather return awaitables
    a = ctx.create_timer(0.1)
    b = ctx.create_timer(0.2)

    all_aw = ctx.when_all([a, b])
    any_aw = ctx.when_any([a, b])
    gat_aw = ctx.gather(a, b)
    gat_exc_aw = ctx.gather(a, b, return_exceptions=True)

    for x in (all_aw, any_aw, gat_aw, gat_exc_aw):
        assert hasattr(x, "__await__")


def test_deterministic_utils_and_passthroughs():
    base = DummyBaseCtx()
    ctx = AsyncWorkflowContext(base)

    rnd = ctx.random()
    # should behave like a random.Random-like object; test a stable first value
    val = rnd.random()
    # Just assert it is within (0,1) and stable across two calls to the seeded RNG instance
    assert 0.0 < val < 1.0
    assert rnd.random() != val  # next value changes

    uid = ctx.uuid4()
    # Should be a UUID-like string representation
    assert isinstance(str(uid), str) and len(str(uid)) >= 32

    # passthroughs
    ctx.set_custom_status("hello")
    assert base._custom_status == "hello"

    ctx.continue_as_new({"x": 1}, save_events=True)
    assert base._continued == ({"x": 1}, True)
