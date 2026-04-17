import subprocess
import threading
import time

import pytest

from dapr.clients.grpc._response import ConfigurationResponse

STORE = 'configurationstore'
REDIS_CONTAINER = 'dapr_redis'


def _redis_set(key: str, value: str, version: int = 1) -> None:
    """Seed a configuration value directly in Redis.

    Dapr's Redis configuration store encodes values as ``value||version``.
    """
    subprocess.run(
        args=('docker', 'exec', REDIS_CONTAINER, 'redis-cli', 'SET', key, f'"{value}||{version}"'),
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope='module')
def client(dapr_env):
    _redis_set('cfg-key-1', 'val-1')
    _redis_set('cfg-key-2', 'val-2')
    return dapr_env.start_sidecar(app_id='test-config')


class TestGetConfiguration:
    def test_get_single_key(self, client):
        resp = client.get_configuration(store_name=STORE, keys=['cfg-key-1'])
        assert 'cfg-key-1' in resp.items
        assert resp.items['cfg-key-1'].value == 'val-1'

    def test_get_multiple_keys(self, client):
        resp = client.get_configuration(store_name=STORE, keys=['cfg-key-1', 'cfg-key-2'])
        assert resp.items['cfg-key-1'].value == 'val-1'
        assert resp.items['cfg-key-2'].value == 'val-2'

    def test_get_missing_key_returns_empty_items(self, client):
        resp = client.get_configuration(store_name=STORE, keys=['nonexistent-cfg-key'])
        # Dapr omits keys that don't exist from the response.
        assert 'nonexistent-cfg-key' not in resp.items

    def test_items_have_version(self, client):
        resp = client.get_configuration(store_name=STORE, keys=['cfg-key-1'])
        item = resp.items['cfg-key-1']
        assert item.version


class TestSubscribeConfiguration:
    def test_subscribe_receives_update(self, client):
        received: list[ConfigurationResponse] = []
        event = threading.Event()

        def handler(_id: str, resp: ConfigurationResponse) -> None:
            received.append(resp)
            event.set()

        sub_id = client.subscribe_configuration(
            store_name=STORE, keys=['cfg-sub-key'], handler=handler
        )
        assert sub_id

        # Give the subscription watcher thread time to establish its gRPC
        # stream before pushing the update, otherwise the notification is missed.
        time.sleep(1)
        _redis_set('cfg-sub-key', 'updated-val', version=2)
        event.wait(timeout=10)

        assert len(received) >= 1
        last = received[-1]
        assert 'cfg-sub-key' in last.items
        assert last.items['cfg-sub-key'].value == 'updated-val'

        ok = client.unsubscribe_configuration(store_name=STORE, id=sub_id)
        assert ok

    def test_unsubscribe_returns_true(self, client):
        sub_id = client.subscribe_configuration(
            store_name=STORE,
            keys=['cfg-unsub-key'],
            handler=lambda _id, _resp: None,
        )
        time.sleep(1)
        ok = client.unsubscribe_configuration(store_name=STORE, id=sub_id)
        assert ok
