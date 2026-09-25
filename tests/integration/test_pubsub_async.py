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

import asyncio
import json

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import BulkPublishEntry
from tests.naming_utils import unique_name
from tests.wait_utils import wait_until_async

STORE = 'statestore'
PUBSUB = 'pubsub'
TOPIC = 'TOPIC_A'
TOPIC_BULK_STREAM = 'TOPIC_BULK_STREAM_ASYNC'
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


async def _next_message(subscription, timeout: float):
    async def read():
        # next_message() returns None after a transient reconnect; keep reading.
        message = await subscription.next_message()
        while message is None:
            message = await subscription.next_message()
        return message

    return await asyncio.wait_for(read(), timeout=timeout)


async def test_bulk_publish_metadata_reaches_each_event(sidecar):
    """publish_metadata applies to every event, with or without entry metadata of its own.

    Mirrors the sync test. Redis pub/sub has no native TTL, so the runtime turns
    ``ttlInSeconds`` into the ``expiration`` cloud event extension. The runtime only merges
    request metadata into entries that already carry metadata, so for the plain entry
    ``expiration`` appears only when the SDK copies ``publish_metadata`` onto it.
    """
    run_id = unique_name()

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        subscription = await d.subscribe(pubsub_name=PUBSUB, topic=TOPIC_BULK_STREAM)
        try:
            response = await d.publish_events(
                pubsub_name=PUBSUB,
                topic_name=TOPIC_BULK_STREAM,
                data=[
                    json.dumps({'run_id': run_id, 'id': 'plain'}),
                    BulkPublishEntry(
                        event=json.dumps({'run_id': run_id, 'id': 'with-metadata'}),
                        metadata={'partitionKey': 'tenant-a'},
                    ),
                ],
                data_content_type='application/json',
                publish_metadata={'ttlInSeconds': '300'},
            )
            assert response.failed_entries == []

            received: dict[str, dict] = {}
            for _ in range(2):
                message = await _next_message(subscription, timeout=10)
                await subscription.respond_success(message)
                payload = message.data()
                assert payload['run_id'] == run_id
                received[payload['id']] = message.extensions()

            assert received.keys() == {'plain', 'with-metadata'}
            for entry, extensions in received.items():
                assert 'expiration' in extensions, f'{entry}: {extensions}'
        finally:
            await subscription.close()
