import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient

STORE = 'localsecretstore'
GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-secrets-async')


async def test_get_secret_returns_expected_value(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.get_secret(store_name=STORE, key='secretKey')

    assert resp.secret == {'secretKey': 'secretValue'}


async def test_get_bulk_secret_returns_all(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.get_bulk_secret(store_name=STORE)

    assert 'secretKey' in resp.secrets
    assert resp.secrets['secretKey'] == {'secretKey': 'secretValue'}
