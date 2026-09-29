import asyncio
import threading
import time
import unittest
from datetime import timedelta

from dapr.credentials.base import WorkloadCredential
from dapr.credentials.manager import AsyncCredentialManager, CredentialManager
from tests.credentials._fakes import FakeProvider, poll_until

BLOCKED_FETCH_TIMEOUT_SECONDS = 2.0


class BlockingProvider(FakeProvider):
    """Blocks every fetch after the first until release() is called."""

    def __init__(self):
        super().__init__(ttl=None)
        self.fetch_started = threading.Event()
        self._release = threading.Event()

    def fetch(self) -> WorkloadCredential:
        if self.fetch_count >= 1:
            self.fetch_started.set()
            self._release.wait(BLOCKED_FETCH_TIMEOUT_SECONDS)
        return super().fetch()

    def release(self) -> None:
        self._release.set()


class CredentialManagerTests(unittest.TestCase):
    def test_fetches_once_for_a_credential_that_never_expires(self):
        provider = FakeProvider(ttl=None)
        manager = CredentialManager(provider)
        manager.get()
        manager.get()
        self.assertEqual(provider.fetch_count, 1)

    def test_fetches_again_after_expiry(self):
        manager = CredentialManager(FakeProvider(ttl=timedelta(milliseconds=20)))
        manager.get()
        self.assertTrue(poll_until(lambda: manager.get().token != 'token-1'))

    def test_start_fetches_and_is_idempotent(self):
        provider = FakeProvider(ttl=None)
        manager = CredentialManager(provider)
        self.addCleanup(manager.close)
        manager.start()
        manager.start()
        self.assertEqual(provider.fetch_count, 1)
        self.assertEqual(manager.current.token, 'token-1')

    def test_does_not_poll_a_credential_that_never_expires(self):
        provider = FakeProvider(ttl=None)
        manager = CredentialManager(provider)
        manager.start()
        self.addCleanup(manager.close)
        time.sleep(0.1)
        self.assertEqual(provider.fetch_count, 1)

    def test_refreshes_ahead_of_expiry(self):
        provider = FakeProvider(ttl=timedelta(milliseconds=50))
        manager = CredentialManager(
            provider, refresh_margin_seconds=0.03, min_refresh_interval_seconds=0.01
        )
        self.addCleanup(manager.close)
        manager.start()
        self.assertTrue(poll_until(lambda: provider.fetch_count >= 3))
        self.assertNotEqual(manager.current.token, 'token-1')

    def test_close_stops_background_refresh(self):
        provider = FakeProvider(ttl=timedelta(milliseconds=30))
        manager = CredentialManager(
            provider, refresh_margin_seconds=0.02, min_refresh_interval_seconds=0.01
        )
        manager.start()
        self.assertTrue(poll_until(lambda: provider.fetch_count >= 2))
        manager.close()
        count_after_close = provider.fetch_count
        time.sleep(0.15)
        self.assertEqual(provider.fetch_count, count_after_close)

    def test_a_failed_refresh_keeps_the_last_credential_and_retries(self):
        provider = FakeProvider(ttl=timedelta(milliseconds=30))
        manager = CredentialManager(
            provider, refresh_margin_seconds=0.02, min_refresh_interval_seconds=0.01
        )
        self.addCleanup(manager.close)
        manager.start()
        self.assertTrue(poll_until(lambda: provider.fetch_count >= 2))
        provider.raise_on_next_fetch = True
        count_before_failure = provider.fetch_count

        with self.assertLogs('dapr.credentials.manager', level='ERROR'):
            self.assertTrue(poll_until(lambda: provider.fetch_count > count_before_failure + 1))

        self.assertIsNotNone(manager.current)

    def test_get_returns_the_cached_credential_while_a_refresh_is_in_flight(self):
        provider = BlockingProvider()
        manager = CredentialManager(provider)
        manager.get()
        refresh = threading.Thread(target=manager.refresh_now)
        refresh.start()
        self.addCleanup(refresh.join)
        self.addCleanup(provider.release)
        self.assertTrue(provider.fetch_started.wait(BLOCKED_FETCH_TIMEOUT_SECONDS))

        started = time.monotonic()
        credential = manager.get()

        self.assertEqual(credential.token, 'token-1')
        self.assertLess(time.monotonic() - started, 0.5)

    def test_refresh_now_replaces_the_credential(self):
        manager = CredentialManager(FakeProvider(ttl=None))
        manager.get()
        manager.refresh_now()
        self.assertEqual(manager.get().token, 'token-2')


class AsyncCredentialManagerWithoutLoopTests(unittest.TestCase):
    def test_get_is_reusable_across_independent_event_loops(self):
        # DaprInvocationHttpClient.invoke_method runs each call on a new event loop.
        provider = FakeProvider(ttl=None)
        manager = AsyncCredentialManager(provider)

        for _ in range(3):
            loop = asyncio.new_event_loop()
            try:
                credential = loop.run_until_complete(manager.get())
            finally:
                loop.close()
            self.assertEqual(credential.token, 'token-1')

        self.assertEqual(provider.fetch_count, 1)
        self.assertIsNone(manager.loop)


class AsyncCredentialManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_once_for_a_credential_that_never_expires(self):
        provider = FakeProvider(ttl=None)
        manager = AsyncCredentialManager(provider)
        await manager.get()
        await manager.get()
        self.assertEqual(provider.fetch_count, 1)

    async def test_captures_the_running_loop(self):
        manager = AsyncCredentialManager(FakeProvider())
        self.assertIs(manager.loop, asyncio.get_running_loop())

    async def test_ensure_current_loop_captures_the_loop_for_a_manager_built_outside_one(self):
        manager = await asyncio.to_thread(AsyncCredentialManager, FakeProvider())
        self.assertIsNone(manager.loop)
        manager.ensure_current_loop()
        self.assertIs(manager.loop, asyncio.get_running_loop())

    async def test_start_is_idempotent(self):
        provider = FakeProvider(ttl=None)
        manager = AsyncCredentialManager(provider)
        await manager.start()
        await manager.start()
        self.assertEqual(provider.fetch_count, 1)
        await manager.close()

    async def test_refreshes_ahead_of_expiry(self):
        provider = FakeProvider(ttl=timedelta(milliseconds=50))
        manager = AsyncCredentialManager(
            provider, refresh_margin_seconds=0.03, min_refresh_interval_seconds=0.01
        )
        await manager.start()
        self.addAsyncCleanup(manager.close)
        for _ in range(100):
            if provider.fetch_count >= 3:
                break
            await asyncio.sleep(0.02)
        self.assertGreaterEqual(provider.fetch_count, 3)

    async def test_close_stops_background_refresh(self):
        provider = FakeProvider(ttl=timedelta(milliseconds=30))
        manager = AsyncCredentialManager(
            provider, refresh_margin_seconds=0.02, min_refresh_interval_seconds=0.01
        )
        await manager.start()
        for _ in range(100):
            if provider.fetch_count >= 2:
                break
            await asyncio.sleep(0.01)
        await manager.close()
        count_after_close = provider.fetch_count

        await asyncio.sleep(0.15)

        self.assertEqual(provider.fetch_count, count_after_close)

    async def test_a_failed_refresh_keeps_the_last_credential_and_retries(self):
        provider = FakeProvider(ttl=timedelta(milliseconds=30))
        manager = AsyncCredentialManager(
            provider, refresh_margin_seconds=0.02, min_refresh_interval_seconds=0.01
        )
        await manager.start()
        self.addAsyncCleanup(manager.close)
        provider.raise_on_next_fetch = True
        count_before_failure = provider.fetch_count

        with self.assertLogs('dapr.credentials.manager', level='ERROR'):
            for _ in range(100):
                if provider.fetch_count > count_before_failure + 1:
                    break
                await asyncio.sleep(0.01)

        self.assertGreater(provider.fetch_count, count_before_failure + 1)
        self.assertIsNotNone(manager.current)


if __name__ == '__main__':
    unittest.main()
