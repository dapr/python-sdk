import threading

import pytest
import redis

from dapr.clients.grpc._response import ConfigurationResponse
from tests.wait_utils import wait_until

STORE = 'configurationstore'


@pytest.fixture(scope='module')
def client(dapr_env, redis_set_config):
    redis_set_config('cfg-key-1', 'val-1')
    redis_set_config('cfg-key-2', 'val-2')
    return dapr_env.start_sidecar(app_id='test-config')


@pytest.mark.xfail(
    reason='The sidecar returns the subscription ID before the subscription is active',
)
def test_subscribe_first_update_race(client):
    r = redis.Redis(host='127.0.0.1', port=6379)
    r.ping()
    event = threading.Event()
    sub_id = client.subscribe_configuration(
        store_name=STORE,
        keys=['cfg-race-key'],
        handler=lambda _id, _resp: event.set(),
    )
    assert sub_id
    r.set('cfg-race-key', 'val||1')
    assert event.wait(timeout=2)


def test_get_single_key(client):
    resp = client.get_configuration(store_name=STORE, keys=['cfg-key-1'])
    assert 'cfg-key-1' in resp.items
    assert resp.items['cfg-key-1'].value == 'val-1'


def test_get_multiple_keys(client):
    resp = client.get_configuration(store_name=STORE, keys=['cfg-key-1', 'cfg-key-2'])
    assert resp.items['cfg-key-1'].value == 'val-1'
    assert resp.items['cfg-key-2'].value == 'val-2'


def test_get_missing_key_returns_empty_items(client):
    resp = client.get_configuration(store_name=STORE, keys=['nonexistent-cfg-key'])
    # Dapr omits keys that don't exist from the response.
    assert 'nonexistent-cfg-key' not in resp.items


def test_items_have_version(client):
    resp = client.get_configuration(store_name=STORE, keys=['cfg-key-1'])
    item = resp.items['cfg-key-1']
    assert item.version


def test_subscribe_receives_update(client, redis_set_config):
    received: list[ConfigurationResponse] = []
    event = threading.Event()

    def handler(_id: str, resp: ConfigurationResponse) -> None:
        received.append(resp)
        event.set()

    sub_id = client.subscribe_configuration(store_name=STORE, keys=['cfg-sub-key'], handler=handler)
    assert sub_id

    # This is necessary because the Dapr runtime returns the subscription ID before the Redis
    # configuration component finishes registering the subscription
    def _set_and_check() -> bool:
        redis_set_config('cfg-sub-key', 'updated-val', version=2)
        return event.is_set()

    wait_until(_set_and_check, timeout=10, interval=0.2)

    assert len(received) >= 1
    last = received[-1]
    assert 'cfg-sub-key' in last.items
    assert last.items['cfg-sub-key'].value == 'updated-val'

    ok = client.unsubscribe_configuration(store_name=STORE, id=sub_id)
    assert ok


def test_unsubscribe_returns_true(client):
    sub_id = client.subscribe_configuration(
        store_name=STORE,
        keys=['cfg-unsub-key'],
        handler=lambda _id, _resp: None,
    )
    ok = client.unsubscribe_configuration(store_name=STORE, id=sub_id)
    assert ok
