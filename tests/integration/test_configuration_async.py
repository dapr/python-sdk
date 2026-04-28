import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient

STORE = 'configurationstore'
GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env, redis_set_config):
    redis_set_config('async-cfg-key-1', 'async-val-1')
    dapr_env.start_sidecar(app_id='test-config-async')


async def test_get_configuration_single_key(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.get_configuration(store_name=STORE, keys=['async-cfg-key-1'])

    assert 'async-cfg-key-1' in resp.items
    assert resp.items['async-cfg-key-1'].value == 'async-val-1'


async def test_get_configuration_missing_key_returns_empty_items(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.get_configuration(store_name=STORE, keys=['nonexistent-async-cfg-key'])

    assert 'nonexistent-async-cfg-key' not in resp.items
