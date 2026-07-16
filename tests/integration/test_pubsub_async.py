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
"""

import json

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from tests.naming_utils import unique_name
from tests.wait_utils import wait_until_async

STORE = 'statestore'
PUBSUB = 'pubsub'
TOPIC = 'TOPIC_A'
GRPC_ADDRESS = '127.0.0.1:13501'


async def _fetch_received(d: AsyncDaprClient, key: str) -> bytes | None:
    resp = await d.get_state(store_name=STORE, key=key)
    return resp.data or None


@pytest.fixture(scope='module')
def sidecar(dapr_env, apps_dir, flush_redis):
    dapr_env.start_sidecar(
        app_id='test-subscriber-async',
        app_port=13503,
        app_cmd=f'python3 {apps_dir / "pubsub_subscriber.py"}',
    )


async def test_publish_event_delivers_to_subscriber(sidecar):
    run_id = unique_name()
    key = f'received-{run_id}-1'

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.publish_event(
            pubsub_name=PUBSUB,
            topic_name=TOPIC,
            data=json.dumps({'run_id': run_id, 'id': 1, 'message': 'async hello'}),
            data_content_type='application/json',
        )

        data = await wait_until_async(lambda: _fetch_received(d, key), timeout=10)

    msg = json.loads(data)
    assert msg['message'] == 'async hello'


async def test_publish_events_bulk_delivery(sidecar):
    run_id = unique_name()
    payloads = [
        json.dumps({'run_id': run_id, 'id': n, 'message': f'bulk-async-{n}'}) for n in range(1, 3)
    ]

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        response = await d.publish_events(
            pubsub_name=PUBSUB,
            topic_name=TOPIC,
            data=payloads,
            data_content_type='application/json',
        )
        assert response.failed_entries == []

        for n in range(1, 3):
            key = f'received-{run_id}-{n}'
            data = await wait_until_async(lambda: _fetch_received(d, key), timeout=10)
            msg = json.loads(data)
            assert msg['message'] == f'bulk-async-{n}'
