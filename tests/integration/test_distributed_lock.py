import pytest

from dapr.clients.grpc._response import UnlockResponseStatus

STORE = 'lockstore'

# The distributed lock API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-lock')


def test_try_lock_acquires(client):
    lock = client.try_lock(STORE, 'res-acquire', 'owner-a', expiry_in_seconds=10)
    assert lock.success


def test_try_lock_second_owner_is_rejected(client):
    first = client.try_lock(STORE, 'res-contention', 'owner-a', expiry_in_seconds=10)
    second = client.try_lock(STORE, 'res-contention', 'owner-b', expiry_in_seconds=10)
    assert first.success
    assert not second.success


def test_try_lock_is_truthy_on_success(client):
    lock = client.try_lock(STORE, 'res-truthy', 'owner-a', expiry_in_seconds=10)
    assert bool(lock) is True


def test_try_lock_failed_lock_is_falsy(client):
    client.try_lock(STORE, 'res-falsy', 'owner-a', expiry_in_seconds=10)
    contested = client.try_lock(STORE, 'res-falsy', 'owner-b', expiry_in_seconds=10)
    assert bool(contested) is False


def test_unlock_own_lock(client):
    client.try_lock(STORE, 'res-unlock', 'owner-a', expiry_in_seconds=10)
    resp = client.unlock(STORE, 'res-unlock', 'owner-a')
    assert resp.status == UnlockResponseStatus.success


def test_unlock_wrong_owner(client):
    client.try_lock(STORE, 'res-wrong-owner', 'owner-a', expiry_in_seconds=10)
    resp = client.unlock(STORE, 'res-wrong-owner', 'owner-b')
    assert resp.status == UnlockResponseStatus.lock_belongs_to_others


def test_unlock_nonexistent(client):
    resp = client.unlock(STORE, 'res-does-not-exist', 'owner-a')
    assert resp.status == UnlockResponseStatus.lock_does_not_exist


def test_unlock_frees_resource_for_others(client):
    client.try_lock(STORE, 'res-release', 'owner-a', expiry_in_seconds=10)
    client.unlock(STORE, 'res-release', 'owner-a')
    second = client.try_lock(STORE, 'res-release', 'owner-b', expiry_in_seconds=10)
    assert second.success


def test_context_manager_auto_unlocks(client):
    with client.try_lock(STORE, 'res-ctx', 'owner-a', expiry_in_seconds=10) as lock:
        assert lock

    second = client.try_lock(STORE, 'res-ctx', 'owner-b', expiry_in_seconds=10)
    assert second.success
