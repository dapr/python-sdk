import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients.grpc._response import UnlockResponseStatus

STORE = 'lockstore'
GRPC_ADDRESS = '127.0.0.1:50001'

# The distributed lock API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-lock-async')


async def test_acquire_and_release_lock(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        lock = await d.try_lock(STORE, 'res-async-acquire', 'owner-a', expiry_in_seconds=10)
        assert lock.success

        resp = await d.unlock(STORE, 'res-async-acquire', 'owner-a')
        assert resp.status == UnlockResponseStatus.success


async def test_second_owner_is_rejected(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        first = await d.try_lock(STORE, 'res-async-contention', 'owner-a', expiry_in_seconds=10)
        second = await d.try_lock(STORE, 'res-async-contention', 'owner-b', expiry_in_seconds=10)

    assert first.success
    assert not second.success


async def test_unlock_nonexistent_returns_not_found(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.unlock(STORE, 'res-async-missing', 'owner-a')

    assert resp.status == UnlockResponseStatus.lock_does_not_exist
