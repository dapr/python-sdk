import asyncio
import time
import unittest
from datetime import timedelta

import grpc

from dapr.credentials._grpc import (
    _async_bearer_token,
    _AuthMetadataPlugin,
    build_async_channel_credentials,
    build_channel_credentials,
)
from dapr.credentials.manager import AsyncCredentialManager, CredentialManager
from tests.credentials._fakes import FakeProvider


class AuthMetadataPluginTests(unittest.TestCase):
    def test_calls_back_with_the_token_as_metadata(self):
        calls = []
        plugin = _AuthMetadataPlugin(lambda: 'tok', 'my-key')
        plugin(None, lambda metadata, error: calls.append((metadata, error)))
        self.assertEqual(calls, [((('my-key', 'tok'),), None)])

    def test_calls_back_with_the_error_on_failure(self):
        def raiser():
            raise RuntimeError('boom')

        calls = []
        plugin = _AuthMetadataPlugin(raiser, 'my-key')
        plugin(None, lambda metadata, error: calls.append((metadata, error)))
        self.assertEqual(calls[0][0], ())
        self.assertIsInstance(calls[0][1], RuntimeError)


class BuildChannelCredentialsTests(unittest.TestCase):
    def test_builds_composite_credentials(self):
        manager = CredentialManager(FakeProvider())
        credentials = build_channel_credentials(manager, grpc.ssl_channel_credentials())
        self.assertIsInstance(credentials, grpc.ChannelCredentials)


class BuildAsyncChannelCredentialsTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_composite_credentials(self):
        manager = AsyncCredentialManager(FakeProvider())
        await manager.start()
        self.addAsyncCleanup(manager.close)
        credentials = build_async_channel_credentials(manager, grpc.ssl_channel_credentials())
        self.assertIsInstance(credentials, grpc.ChannelCredentials)


class AsyncBearerTokenFastPathTests(unittest.TestCase):
    """Runs outside any event loop, as gRPC's plugin thread does."""

    def test_returns_the_cached_token_without_a_loop(self):
        manager = AsyncCredentialManager(FakeProvider(ttl=timedelta(seconds=60)))
        asyncio.run(manager.get())

        self.assertEqual(_async_bearer_token(manager, plugin_timeout_seconds=1.0), 'token-1')

    def test_raises_when_the_token_expired_and_no_loop_was_captured(self):
        manager = AsyncCredentialManager(FakeProvider(ttl=timedelta(milliseconds=1)))
        asyncio.run(manager.get())
        time.sleep(0.05)

        with self.assertRaises(RuntimeError):
            _async_bearer_token(manager, plugin_timeout_seconds=1.0)


class AsyncBearerTokenSlowPathTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_on_the_managers_loop_when_expired(self):
        manager = AsyncCredentialManager(FakeProvider(ttl=timedelta(milliseconds=1)))
        await manager.start()
        self.addAsyncCleanup(manager.close)
        await asyncio.sleep(0.05)

        token = await asyncio.to_thread(_async_bearer_token, manager, 1.0)

        self.assertNotEqual(token, 'token-1')


if __name__ == '__main__':
    unittest.main()
