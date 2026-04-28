import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient

GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-metadata-async')


async def test_get_metadata_application_id_matches(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        meta = await d.get_metadata()

    assert meta.application_id == 'test-metadata-async'


async def test_set_and_get_metadata_round_trip(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.set_metadata('async-key', 'async-value')
        meta = await d.get_metadata()

    assert meta.extended_metadata.get('async-key') == 'async-value'
