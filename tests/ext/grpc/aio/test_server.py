# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

End-to-end coverage over a real grpc.aio server, exercising the wiring the unit tests mock
out: servicer registration, the aio context coroutines, and graceful shutdown.
"""

import asyncio
import contextlib
import socket
import unittest

import grpc.aio
from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.empty_pb2 import Empty

from dapr.ext.grpc.aio import (
    App,
    BindingRequest,
    InvokeMethodRequest,
    InvokeMethodResponse,
    JobEvent,
    SubscriptionMessage,
    TopicEventResponse,
)
from dapr.proto import appcallback_service_v1, appcallback_v1, common_v1

RPC_TIMEOUT_SECONDS = 10


def _free_port() -> int:
    """Reserves an ephemeral port for the test server to bind."""
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


async def _wait_until_serving(port: int, run_task: 'asyncio.Task') -> None:
    """Waits until the port actually accepts connections, not merely until it is assigned.

    ``App._server`` is set *before* ``server.start()`` is awaited, so polling it would return
    while the server is still coming up — and a cancellation aimed at the serving app could
    land inside startup instead. ``_free_port`` is also racy, so a bind can fail outright;
    surfacing ``run_task``'s exception beats spinning on a server that will never appear.
    """

    # One channel, closed by this function rather than inside poll(): a close awaited in
    # poll()'s finally would run while wait_for is cancelling it, and could surface as a bare
    # CancelledError instead of the TimeoutError that actually explains the failure.
    channel = grpc.aio.insecure_channel(f'127.0.0.1:{port}')

    async def poll() -> None:
        while True:
            if run_task.done():
                await run_task  # re-raises whatever stopped the server coming up
                raise AssertionError('run() returned before the server was serving')
            try:
                await asyncio.wait_for(channel.channel_ready(), timeout=0.25)
                return
            except asyncio.TimeoutError:
                continue

    try:
        await asyncio.wait_for(poll(), timeout=RPC_TIMEOUT_SECONDS)
    except BaseException:
        # Otherwise run_task keeps its listener for the rest of the session and the loop is
        # torn down under a live task.
        run_task.cancel()
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await run_task
        raise
    finally:
        await channel.close()


class AioAppServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received_events = []
        self.received_bindings = []
        self.received_jobs = []
        self.health_checks = []

        self._app = App()
        self._register_handlers(self._app)

        self._port = _free_port()
        await self._app.start(app_port=self._port, listen_address='127.0.0.1')
        self.addAsyncCleanup(self._app.stop, 0)

        self._channel = grpc.aio.insecure_channel(f'127.0.0.1:{self._port}')
        self.addAsyncCleanup(self._channel.close)
        self.stub = appcallback_service_v1.AppCallbackStub(self._channel)
        self.health_stub = appcallback_service_v1.AppCallbackHealthCheckStub(self._channel)

    def _register_handlers(self, app):
        @app.method('echo')
        async def echo(request: InvokeMethodRequest):
            await asyncio.sleep(0)
            response = InvokeMethodResponse(b'async-pong', 'text/plain')
            response.headers = (('x-custom', 'header-value'),)
            return response

        @app.subscribe(pubsub_name='pubsub', topic='orders')
        async def on_order(event: SubscriptionMessage) -> TopicEventResponse:
            await asyncio.sleep(0)
            self.received_events.append(event.data())
            return TopicEventResponse('success')

        @app.binding('input')
        async def on_binding(request: BindingRequest) -> None:
            await asyncio.sleep(0)
            self.received_bindings.append(request.text())

        @app.job_event('nightly')
        async def on_job(event: JobEvent) -> None:
            await asyncio.sleep(0)
            self.received_jobs.append(event.get_data_as_string())

        async def health_check() -> None:
            self.health_checks.append(True)

        app.register_health_check(health_check)

    async def test_async_method_handler_returns_data_and_headers(self):
        call = self.stub.OnInvoke(
            common_v1.InvokeRequest(method='echo', data=GrpcAny()),
            timeout=RPC_TIMEOUT_SECONDS,
        )
        response = await call
        initial_metadata = dict(await call.initial_metadata())

        self.assertEqual(b'async-pong', response.data.value)
        self.assertEqual('text/plain', response.content_type)
        self.assertEqual('header-value', initial_metadata.get('x-custom'))

    async def test_unregistered_method_is_unimplemented(self):
        with self.assertRaises(grpc.aio.AioRpcError) as exception_context:
            await self.stub.OnInvoke(
                common_v1.InvokeRequest(method='missing', data=GrpcAny()),
                timeout=RPC_TIMEOUT_SECONDS,
            )

        self.assertEqual(grpc.StatusCode.UNIMPLEMENTED, exception_context.exception.code())

    async def test_list_topic_subscriptions(self):
        response = await self.stub.ListTopicSubscriptions(Empty(), timeout=RPC_TIMEOUT_SECONDS)

        self.assertEqual(
            [('pubsub', 'orders')],
            [(sub.pubsub_name, sub.topic) for sub in response.subscriptions],
        )

    async def test_async_topic_handler_receives_event(self):
        request = appcallback_v1.TopicEventRequest(
            id='event-1',
            pubsub_name='pubsub',
            topic='orders',
            data=b'{"id": 1}',
            data_content_type='application/json',
        )

        response = await self.stub.OnTopicEvent(request, timeout=RPC_TIMEOUT_SECONDS)

        self.assertEqual([{'id': 1}], self.received_events)
        self.assertEqual(
            appcallback_v1.TopicEventResponse.TopicEventResponseStatus.SUCCESS, response.status
        )

    async def test_list_input_bindings(self):
        response = await self.stub.ListInputBindings(Empty(), timeout=RPC_TIMEOUT_SECONDS)

        self.assertEqual(['input'], list(response.bindings))

    async def test_async_binding_handler_receives_event(self):
        request = appcallback_v1.BindingEventRequest(name='input', data=b'binding-payload')

        await self.stub.OnBindingEvent(request, timeout=RPC_TIMEOUT_SECONDS)

        self.assertEqual(['binding-payload'], self.received_bindings)

    async def test_async_job_handler_receives_event(self):
        request = appcallback_v1.JobEventRequest(name='nightly', data=GrpcAny(value=b'job-payload'))

        await self.stub.OnJobEvent(request, timeout=RPC_TIMEOUT_SECONDS)

        self.assertEqual(['job-payload'], self.received_jobs)

    async def test_async_health_check(self):
        await self.health_stub.HealthCheck(Empty(), timeout=RPC_TIMEOUT_SECONDS)

        self.assertEqual([True], self.health_checks)

    async def test_concurrent_requests_are_not_serialized(self):
        """A request must complete while an earlier, still-blocked one is in flight.

        The slow handler is confirmed to be inside its await before the fast request is
        sent, so a serialized dispatcher would deadlock rather than pass.
        """
        slow_entered = asyncio.Event()
        release_slow = asyncio.Event()
        completion_order = []
        app = App()

        @app.method('slow')
        async def slow(request: InvokeMethodRequest):
            slow_entered.set()
            await release_slow.wait()
            completion_order.append('slow')
            return b'slow-done'

        @app.method('fast')
        async def fast(request: InvokeMethodRequest):
            completion_order.append('fast')
            release_slow.set()
            return b'fast-done'

        port = _free_port()
        await app.start(app_port=port, listen_address='127.0.0.1')
        try:
            async with grpc.aio.insecure_channel(f'127.0.0.1:{port}') as channel:
                stub = appcallback_service_v1.AppCallbackStub(channel)

                slow_task = asyncio.ensure_future(
                    stub.OnInvoke(
                        common_v1.InvokeRequest(method='slow', data=GrpcAny()),
                        timeout=RPC_TIMEOUT_SECONDS,
                    )
                )
                # Only send the second request once the first is provably blocked.
                await asyncio.wait_for(slow_entered.wait(), timeout=RPC_TIMEOUT_SECONDS)

                fast_response = await asyncio.wait_for(
                    stub.OnInvoke(
                        common_v1.InvokeRequest(method='fast', data=GrpcAny()),
                        timeout=RPC_TIMEOUT_SECONDS,
                    ),
                    timeout=RPC_TIMEOUT_SECONDS,
                )
                slow_response = await asyncio.wait_for(slow_task, timeout=RPC_TIMEOUT_SECONDS)

            self.assertEqual(['fast', 'slow'], completion_order)
            self.assertEqual(b'slow-done', slow_response.data.value)
            self.assertEqual(b'fast-done', fast_response.data.value)
        finally:
            await app.stop(grace=0)


class AioAppRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_serves_until_stopped(self):
        app = App()

        @app.method('ping')
        async def ping(request: InvokeMethodRequest):
            return b'pong'

        port = _free_port()
        run_task = asyncio.create_task(app.run(app_port=port, listen_address='127.0.0.1'))
        await _wait_until_serving(port, run_task)

        try:
            async with grpc.aio.insecure_channel(f'127.0.0.1:{port}') as channel:
                stub = appcallback_service_v1.AppCallbackStub(channel)
                response = await asyncio.wait_for(
                    stub.OnInvoke(
                        common_v1.InvokeRequest(method='ping', data=GrpcAny()),
                        timeout=RPC_TIMEOUT_SECONDS,
                    ),
                    timeout=RPC_TIMEOUT_SECONDS,
                )
            self.assertEqual(b'pong', response.data.value)
        finally:
            await app.stop(grace=0)

        await asyncio.wait_for(run_task, timeout=RPC_TIMEOUT_SECONDS)

    async def test_run_releases_the_server_when_cancelled(self):
        """Cancelling run() must stop the server rather than leave the port bound.

        The synchronous App stops its server from __del__; a coroutine cannot be awaited
        from one, so run() has to clean up after itself.
        """
        app = App()

        @app.method('ping')
        async def ping(request: InvokeMethodRequest):
            return b'pong'

        port = _free_port()
        run_task = asyncio.create_task(app.run(app_port=port, listen_address='127.0.0.1'))
        await _wait_until_serving(port, run_task)

        run_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await run_task

        self.assertIsNone(app._server)

        channel = grpc.aio.insecure_channel(f'127.0.0.1:{port}')
        try:
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(channel.channel_ready(), timeout=2)
        finally:
            await channel.close()

        # The app must be reusable, not wedged by a stale _server reference.
        await app.start(app_port=_free_port(), listen_address='127.0.0.1')
        await app.stop(grace=0)


class AppLoopBindingTests(unittest.TestCase):
    """The lifecycle lock binds to a loop, so loop identity is part of the contract.

    These run their own ``asyncio.run`` blocks rather than using IsolatedAsyncioTestCase,
    because the behaviour under test is precisely what happens across separate loops.
    """

    def test_reuse_on_a_second_loop_after_a_clean_stop(self):
        app = App()
        port_one, port_two = _free_port(), _free_port()

        async def cycle(port):
            await app.start(app_port=port, listen_address='127.0.0.1')
            await app.stop(grace=0)

        asyncio.run(cycle(port_one))
        asyncio.run(cycle(port_two))  # must not raise "bound to a different event loop"

    def test_foreign_loop_while_owning_loop_is_alive_raises(self):
        app = App()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(app.start(app_port=_free_port(), listen_address='127.0.0.1'))

            async def stop_from_elsewhere():
                await app.stop(grace=0)

            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(stop_from_elsewhere())
            self.assertIn('different event loop', str(ctx.exception))
        finally:
            # In the finally: if the guard ever regresses the assertion fails here, and an
            # un-stopped server would leak a bound port into every later test.
            if app._server is not None:
                loop.run_until_complete(app.stop(grace=0))
            loop.close()


class AppStartFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_bind_failure_leaves_no_dangling_server(self):
        """A taken port must not strand the server built for it."""
        holder = socket.socket()
        holder.bind(('127.0.0.1', 0))
        holder.listen()
        self.addCleanup(holder.close)
        taken_port = holder.getsockname()[1]

        app = App()
        with self.assertRaises(RuntimeError):
            await app.start(app_port=taken_port, listen_address='127.0.0.1')
        self.assertIsNone(app._server)

        # and the App is still usable afterwards
        await app.start(app_port=_free_port(), listen_address='127.0.0.1')
        await app.stop(grace=0)

    async def test_cancelled_drain_clears_the_server_and_closes_the_port(self):
        """A graceful stop that is cut short must leave the App stopped and the port free.

        grpc closes the listener as soon as the drain begins, so this pins the observable
        contract rather than the forced ``stop(None)`` specifically; that call is defensive.
        """
        app = App()

        @app.method('slow')
        async def slow(request: InvokeMethodRequest):
            await asyncio.sleep(30)
            return b'never'

        port = _free_port()
        await app.start(app_port=port, listen_address='127.0.0.1')

        async with grpc.aio.insecure_channel(f'127.0.0.1:{port}') as channel:
            stub = appcallback_service_v1.AppCallbackStub(channel)
            in_flight = asyncio.ensure_future(
                stub.OnInvoke(common_v1.InvokeRequest(method='slow', data=GrpcAny()))
            )
            await asyncio.sleep(0.2)

            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(app.stop(grace=30), timeout=1)

            in_flight.cancel()

        self.assertIsNone(app._server)
        probe = grpc.aio.insecure_channel(f'127.0.0.1:{port}')
        try:
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(probe.channel_ready(), timeout=2)
        finally:
            await probe.close()


if __name__ == '__main__':
    unittest.main()
