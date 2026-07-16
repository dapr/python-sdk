# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

End-to-end tests for actor hosting over the gRPC stream (alpha).

The actor host runs as a subprocess (apps/actor_grpc_host.py) and receives all
callbacks over SubscribeActorEventsAlpha1. Tests drive it from the outside via
ActorProxy and assert on values the actor persisted in its state store, so
invoke, reminders, timers, deactivation, and the gRPC outbound operations are
all exercised against a real daprd.

Requires a daprd build that supports SubscribeActorEventsAlpha1; the module is
skipped otherwise.
"""

import asyncio
import json
import time

import pytest

from dapr.actor import ActorId, ActorProxy
from tests.actor_grpc_utils import actor_stream_supported

GRPC_PORT = 13531
HTTP_PORT = 3531
APP_PORT = 9131

ACTOR_TYPE = 'GrpcIntegrationActor'
ACTOR_ID = 'integration-1'


def _invoke(method: str, data: bytes = None):
    async def _run():
        proxy = ActorProxy.create(ACTOR_TYPE, ActorId(ACTOR_ID))
        return await proxy.invoke_method(method, data)

    return json.loads(asyncio.run(_run()))


def _invoke_until(method: str, predicate, timeout: float, interval: float = 1.0):
    deadline = time.monotonic() + timeout
    last_result = None
    while time.monotonic() < deadline:
        last_result = _invoke(method)
        if predicate(last_result):
            return last_result
        time.sleep(interval)
    raise AssertionError(f'{method} never satisfied predicate, last result: {last_result}')


@pytest.fixture(scope='module')
def actor_host(dapr_env, apps_dir):
    dapr_env.start_sidecar(
        app_id='actor-grpc-host',
        grpc_port=GRPC_PORT,
        http_port=HTTP_PORT,
        app_port=APP_PORT,
        app_cmd=f'python3 {apps_dir / "actor_grpc_host.py"}',
    )
    if not actor_stream_supported(GRPC_PORT):
        pytest.skip('daprd does not support SubscribeActorEventsAlpha1')

    # The first invocation needs the placement table and the stream
    # registration to settle; retry until the actor responds.
    deadline = time.monotonic() + 30
    while True:
        try:
            _invoke('GetActivationCount')
            break
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


def test_invoke_and_state_round_trip(actor_host):
    _invoke('SetData', json.dumps({'x': 1}).encode('utf-8'))

    assert _invoke('GetData') == {'x': 1}
    assert _invoke('GetActivationCount') >= 1


def test_reminder_fires_over_stream(actor_host):
    _invoke('StartReminder')
    try:
        evidence = _invoke_until('GetReminderEvidence', lambda value: value == 'rstate', timeout=20)
    finally:
        _invoke('StopReminder')
    assert evidence == 'rstate'


def test_timer_fires_over_stream(actor_host):
    _invoke('StartTimer')
    try:
        evidence = _invoke_until('GetTimerEvidence', lambda value: value == {'n': 7}, timeout=20)
    finally:
        _invoke('StopTimer')
    assert evidence == {'n': 7}


def test_idle_actor_is_deactivated_and_reactivates(actor_host):
    """The host's idle timeout is 3s; daprd's deactivation scan eventually
    deactivates the instance and the next invocation activates a fresh one,
    bumping the persisted activation counter.

    Slow by design: the scan interval is daprd-side (default 30s) and cannot
    be configured over the stream.
    """
    initial_count = _invoke('GetActivationCount')

    # Each poll resets the idle clock, so poll on a period much larger than
    # the idle timeout to leave room for the deactivation scan.
    _invoke_until(
        'GetActivationCount',
        lambda count: count > initial_count,
        timeout=120,
        interval=10,
    )
