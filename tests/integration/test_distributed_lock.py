import pytest

from dapr.clients.grpc._response import UnlockResponseStatus

STORE = 'lockstore'

# The distributed lock API emits alpha warnings on every call.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-lock')


class TestTryLock:
    def test_acquire_lock(self, client):
        lock = client.try_lock(STORE, 'res-acquire', 'owner-a', expiry_in_seconds=10)
        assert lock.success

    def test_second_owner_is_rejected(self, client):
        first = client.try_lock(STORE, 'res-contention', 'owner-a', expiry_in_seconds=10)
        second = client.try_lock(STORE, 'res-contention', 'owner-b', expiry_in_seconds=10)
        assert first.success
        assert not second.success

    def test_lock_is_truthy_on_success(self, client):
        lock = client.try_lock(STORE, 'res-truthy', 'owner-a', expiry_in_seconds=10)
        assert bool(lock) is True

    def test_failed_lock_is_falsy(self, client):
        client.try_lock(STORE, 'res-falsy', 'owner-a', expiry_in_seconds=10)
        contested = client.try_lock(STORE, 'res-falsy', 'owner-b', expiry_in_seconds=10)
        assert bool(contested) is False


class TestUnlock:
    def test_unlock_own_lock(self, client):
        client.try_lock(STORE, 'res-unlock', 'owner-a', expiry_in_seconds=10)
        resp = client.unlock(STORE, 'res-unlock', 'owner-a')
        assert resp.status == UnlockResponseStatus.success

    def test_unlock_wrong_owner(self, client):
        client.try_lock(STORE, 'res-wrong-owner', 'owner-a', expiry_in_seconds=10)
        resp = client.unlock(STORE, 'res-wrong-owner', 'owner-b')
        assert resp.status == UnlockResponseStatus.lock_belongs_to_others

    def test_unlock_nonexistent(self, client):
        resp = client.unlock(STORE, 'res-does-not-exist', 'owner-a')
        assert resp.status == UnlockResponseStatus.lock_does_not_exist

    def test_unlock_frees_resource_for_others(self, client):
        client.try_lock(STORE, 'res-release', 'owner-a', expiry_in_seconds=10)
        client.unlock(STORE, 'res-release', 'owner-a')
        second = client.try_lock(STORE, 'res-release', 'owner-b', expiry_in_seconds=10)
        assert second.success


class TestLockContextManager:
    def test_context_manager_auto_unlocks(self, client):
        with client.try_lock(STORE, 'res-ctx', 'owner-a', expiry_in_seconds=10) as lock:
            assert lock

        # After the context manager exits, another owner should be able to acquire.
        second = client.try_lock(STORE, 'res-ctx', 'owner-b', expiry_in_seconds=10)
        assert second.success
