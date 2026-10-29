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
"""

import inspect
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock

from cloudevents.sdk.event import v1
from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.clients.grpc._request import InvokeMethodRequest
from dapr.clients.grpc._response import InvokeMethodResponse, TopicEventResponse
from dapr.common.pubsub.subscription import SubscriptionMessage
from dapr.ext.grpc._health_servicer import _HealthCheckServicer
from dapr.ext.grpc._servicer import _CallbackServicer
from dapr.ext.grpc.aio._health_servicer import _AioHealthCheckServicer
from dapr.ext.grpc.aio._servicer import _AioCallbackServicer
from dapr.proto import appcallback_service_v1, appcallback_v1, common_v1
from dapr.proto.runtime.v1.appcallback_pb2 import (
    TopicEventBulkRequest,
    TopicEventBulkRequestEntry,
    TopicEventCERequest,
)

DEFAULT_INVOCATION_METADATA = (('key1', 'value1'), ('key2', 'value1'))


def fake_aio_context(invocation_metadata=DEFAULT_INVOCATION_METADATA):
    """Mocks a grpc.aio ServicerContext.

    ``invocation_metadata`` is synchronous on the aio context while
    ``send_initial_metadata`` is a coroutine, so the two are mocked differently.
    """
    context = MagicMock()
    context.invocation_metadata.return_value = invocation_metadata
    context.send_initial_metadata = AsyncMock()
    return context


class OnInvokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._servicer = _AioCallbackServicer()
        self.fake_context = fake_aio_context()

    async def _on_invoke(self, method_name, method_cb):
        self._servicer.register_method(method_name, method_cb)

        return await self._servicer.OnInvoke(
            common_v1.InvokeRequest(method=method_name, data=GrpcAny()),
            self.fake_context,
        )

    async def test_on_invoke_return_str(self):
        async def method_cb(request: InvokeMethodRequest):
            return 'method_str_cb'

        resp = await self._on_invoke('method_str', method_cb)

        self.assertEqual(b'method_str_cb', resp.data.value)

    async def test_on_invoke_return_bytes(self):
        async def method_cb(request: InvokeMethodRequest):
            return b'method_str_cb'

        resp = await self._on_invoke('method_bytes', method_cb)

        self.assertEqual(b'method_str_cb', resp.data.value)

    async def test_on_invoke_return_proto(self):
        async def method_cb(request: InvokeMethodRequest):
            return common_v1.StateItem(key='fake_key')

        resp = await self._on_invoke('method_proto', method_cb)

        state = common_v1.StateItem()
        resp.data.Unpack(state)

        self.assertEqual('fake_key', state.key)

    async def test_on_invoke_return_invoke_method_response(self):
        async def method_cb(request: InvokeMethodRequest):
            return InvokeMethodResponse(data='fake_data', content_type='text/plain')

        resp = await self._on_invoke('method_resp', method_cb)

        self.assertEqual(b'fake_data', resp.data.value)
        self.assertEqual('text/plain', resp.content_type)

    async def test_on_invoke_invalid_response(self):
        async def method_cb(request: InvokeMethodRequest):
            return 1000

        with self.assertRaises(NotImplementedError):
            await self._on_invoke('method_resp', method_cb)

    async def test_on_invoke_awaits_send_initial_metadata(self):
        """Headers are sent through the aio context's coroutine, not a bare call."""

        async def method_cb(request: InvokeMethodRequest):
            resp = InvokeMethodResponse(data='fake_data', content_type='text/plain')
            resp.headers = (('x-custom', 'header-value'),)
            return resp

        await self._on_invoke('method_headers', method_cb)

        self.fake_context.send_initial_metadata.assert_awaited_once()

    async def test_on_invoke_receives_invocation_metadata(self):
        received = []

        async def method_cb(request: InvokeMethodRequest):
            received.append(request.metadata)
            return 'ok'

        await self._on_invoke('method_metadata', method_cb)

        self.assertEqual({'key1': ['value1'], 'key2': ['value1']}, received[0])

    async def test_on_invoke_accepts_sync_handler(self):
        def method_cb(request: InvokeMethodRequest):
            return 'sync_result'

        resp = await self._on_invoke('method_sync', method_cb)

        self.assertEqual(b'sync_result', resp.data.value)

    async def test_non_registered_method(self):
        with self.assertRaises(NotImplementedError):
            await self._servicer.OnInvoke(
                common_v1.InvokeRequest(method='unknown', data=GrpcAny()),
                self.fake_context,
            )


class TopicSubscriptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._servicer = _AioCallbackServicer()
        self._topic_method = AsyncMock(return_value=None)
        self._servicer.register_topic('pubsub1', 'topic1', self._topic_method, {'session': 'key'})
        self.fake_context = fake_aio_context()

    def _request(self, topic='topic1', pubsub_name='pubsub1', path=''):
        return appcallback_v1.TopicEventRequest(
            id='event-1',
            data_content_type='application/json',
            data=b'{"a": 1}',
            topic=topic,
            pubsub_name=pubsub_name,
            path=path,
        )

    def test_duplicated_topic(self):
        with self.assertRaises(ValueError):
            self._servicer.register_topic('pubsub1', 'topic1', self._topic_method, {})

    async def test_list_topic_subscription(self):
        resp = await self._servicer.ListTopicSubscriptions(None, self.fake_context)

        self.assertEqual('pubsub1', resp.subscriptions[0].pubsub_name)
        self.assertEqual('topic1', resp.subscriptions[0].topic)

    async def test_topic_event_awaits_handler(self):
        await self._servicer.OnTopicEvent(self._request(), self.fake_context)

        self._topic_method.assert_awaited_once()

    async def test_topic_event_response_status(self):
        self._topic_method.return_value = TopicEventResponse('retry')

        resp = await self._servicer.OnTopicEvent(self._request(), self.fake_context)

        self.assertEqual(
            appcallback_v1.TopicEventResponse.TopicEventResponseStatus.RETRY, resp.status
        )

    async def test_topic_event_accepts_sync_handler(self):
        sync_handler = Mock(return_value=TopicEventResponse('drop'))
        self._servicer.register_topic('pubsub2', 'topic2', sync_handler, {})

        resp = await self._servicer.OnTopicEvent(
            self._request(topic='topic2', pubsub_name='pubsub2'), self.fake_context
        )

        sync_handler.assert_called_once()
        self.assertEqual(
            appcallback_v1.TopicEventResponse.TopicEventResponseStatus.DROP, resp.status
        )

    async def test_non_registered_topic(self):
        with self.assertRaises(NotImplementedError):
            await self._servicer.OnTopicEvent(self._request(topic='unknown'), self.fake_context)


class BulkTopicEventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._servicer = _AioCallbackServicer()
        self._topic_method = AsyncMock(return_value=TopicEventResponse('success'))
        self._servicer.register_topic('pubsub1', 'topic1', self._topic_method, {'session': 'key'})
        self.fake_context = fake_aio_context()

    def _request(self, entries, topic='topic1'):
        return TopicEventBulkRequest(
            id='bulk1',
            pubsub_name='pubsub1',
            topic=topic,
            path='',
            entries=entries,
        )

    async def test_on_bulk_topic_event(self):
        entry1 = TopicEventBulkRequestEntry(
            entry_id='entry1', bytes=b'hello', content_type='text/plain'
        )
        entry2 = TopicEventBulkRequestEntry(
            entry_id='entry2', bytes=b'{"a": 1}', content_type='application/json'
        )

        resp = await self._servicer.OnBulkTopicEvent(
            self._request([entry1, entry2]), self.fake_context
        )

        self.assertEqual(2, len(resp.statuses))
        self.assertEqual('entry1', resp.statuses[0].entry_id)
        self.assertEqual('entry2', resp.statuses[1].entry_id)
        self.assertEqual(
            appcallback_v1.TopicEventResponse.TopicEventResponseStatus.SUCCESS,
            resp.statuses[0].status,
        )
        self.assertEqual(2, self._topic_method.await_count)

    async def test_on_bulk_topic_event_cloud_event_entry(self):
        cloud_event = TopicEventCERequest(
            id='ce-1',
            source='ce-source',
            type='ce.type',
            spec_version='1.0',
            data_content_type='application/json',
            data=b'{"a": 1}',
        )
        entry = TopicEventBulkRequestEntry(entry_id='entry1', cloud_event=cloud_event)

        resp = await self._servicer.OnBulkTopicEvent(self._request([entry]), self.fake_context)

        self.assertEqual(1, len(resp.statuses))
        delivered = self._topic_method.await_args[0][0]
        self.assertEqual('ce-1', delivered.EventID())

    async def test_on_bulk_topic_event_handler_raises_retry(self):
        self._topic_method.side_effect = ValueError('handler exploded')
        entry = TopicEventBulkRequestEntry(entry_id='entry1', bytes=b'hello')

        resp = await self._servicer.OnBulkTopicEvent(self._request([entry]), self.fake_context)

        self.assertEqual(
            appcallback_v1.TopicEventResponse.TopicEventResponseStatus.RETRY,
            resp.statuses[0].status,
        )

    async def test_on_bulk_topic_event_alpha1(self):
        entry = TopicEventBulkRequestEntry(entry_id='entry1', bytes=b'hello')

        with self.assertWarns(DeprecationWarning):
            resp = await self._servicer.OnBulkTopicEventAlpha1(
                self._request([entry]), self.fake_context
            )

        self.assertEqual(1, len(resp.statuses))

    async def test_on_bulk_topic_event_non_registered(self):
        entry = TopicEventBulkRequestEntry(entry_id='entry1', bytes=b'hello')

        with self.assertRaises(NotImplementedError):
            await self._servicer.OnBulkTopicEvent(
                self._request([entry], topic='unknown'), self.fake_context
            )


class BindingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._servicer = _AioCallbackServicer()
        self._binding_method = AsyncMock(return_value=None)
        self._servicer.register_binding('binding1', self._binding_method)
        self.fake_context = fake_aio_context()

    def test_duplicated_binding(self):
        with self.assertRaises(ValueError):
            self._servicer.register_binding('binding1', self._binding_method)

    async def test_list_bindings(self):
        resp = await self._servicer.ListInputBindings(None, self.fake_context)

        self.assertEqual(['binding1'], list(resp.bindings))

    async def test_binding_event_awaits_handler(self):
        request = appcallback_v1.BindingEventRequest(name='binding1', data=b'hello')

        resp = await self._servicer.OnBindingEvent(request, self.fake_context)

        self.assertIsInstance(resp, appcallback_v1.BindingEventResponse)
        self._binding_method.assert_awaited_once()
        self.assertEqual(b'hello', self._binding_method.await_args[0][0].data)

    async def test_non_registered_binding(self):
        request = appcallback_v1.BindingEventRequest(name='unknown', data=b'hello')

        with self.assertRaises(NotImplementedError):
            await self._servicer.OnBindingEvent(request, self.fake_context)


class JobEventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._servicer = _AioCallbackServicer()
        self._handler = AsyncMock(return_value=None)
        self._servicer.register_job_event('test-job', self._handler)
        self.fake_context = fake_aio_context()

    def _request(self, name='test-job', payload=b'hello'):
        return appcallback_v1.JobEventRequest(name=name, data=GrpcAny(value=payload))

    def test_duplicated_job_event(self):
        with self.assertRaises(ValueError):
            self._servicer.register_job_event('test-job', self._handler)

    async def test_on_job_event_stable_routes_to_handler(self):
        resp = await self._servicer.OnJobEvent(self._request(), self.fake_context)

        self.assertIsInstance(resp, appcallback_v1.JobEventResponse)
        self._handler.assert_awaited_once()
        job_event = self._handler.await_args[0][0]
        self.assertEqual('test-job', job_event.name)
        self.assertEqual('hello', job_event.get_data_as_string())

    async def test_on_job_event_alpha1_routes_to_same_handler(self):
        resp = await self._servicer.OnJobEventAlpha1(self._request(), self.fake_context)

        self.assertIsInstance(resp, appcallback_v1.JobEventResponse)
        self._handler.assert_awaited_once()

    async def test_non_registered_job_event(self):
        with self.assertRaises(NotImplementedError):
            await self._servicer.OnJobEvent(self._request(name='unknown-job'), self.fake_context)


class TopicEventTypeDeliveryTests(unittest.IsolatedAsyncioTestCase):
    """The aio servicer honours the same legacy-cloudevent opt-out as the sync one."""

    def setUp(self):
        self._servicer = _AioCallbackServicer()
        self.fake_context = fake_aio_context(invocation_metadata=(('trace', 'abc'),))

    async def _deliver(self, legacy_cloudevent):
        handler = AsyncMock(return_value=None)
        self._servicer.register_topic(
            'pubsub1', 'topic1', handler, {}, legacy_cloudevent=legacy_cloudevent
        )
        request = appcallback_v1.TopicEventRequest(
            id='event-1',
            data_content_type='application/json',
            data=b'{"a": 1}',
            topic='topic1',
            pubsub_name='pubsub1',
        )

        await self._servicer.OnTopicEvent(request, self.fake_context)

        return handler.await_args[0][0]

    async def test_legacy_default_delivers_cloudevent(self):
        event = await self._deliver(legacy_cloudevent=True)

        self.assertIsInstance(event, v1.Event)
        self.assertEqual('event-1', event.EventID())
        self.assertEqual('abc', event.Extensions()['_metadata_trace'])

    async def test_opt_out_delivers_subscription_message(self):
        event = await self._deliver(legacy_cloudevent=False)

        self.assertIsInstance(event, SubscriptionMessage)
        self.assertEqual('event-1', event.id())
        self.assertEqual({'a': 1}, event.data())


class AsyncParityTests(unittest.TestCase):
    """Guards the sync/aio servicer pair against drifting apart."""

    def _rpc_names_for(self, generated, sync_cls):
        """RPC names the sync servicer implements, anywhere in its MRO above the stubs."""
        generated_rpc_names = {
            name for servicer in generated for name in vars(servicer) if not name.startswith('_')
        }
        # Union over the MRO, not vars(sync_cls): an RPC deduplicated onto a shared base
        # would otherwise drop out of the guard silently.
        sync_implemented = set()
        for klass in sync_cls.__mro__:
            if klass in generated:
                break
            sync_implemented |= set(vars(klass))
        return sorted(generated_rpc_names & sync_implemented)

    def test_health_servicer_pair_stays_in_parity(self):
        """The health servicer pair needs the same guard as the callback pair."""
        generated = (appcallback_service_v1.AppCallbackHealthCheckServicer,)
        names = self._rpc_names_for(generated, _HealthCheckServicer)
        self.assertNotEqual([], names)

        for name in names:
            with self.subTest(rpc=name):
                aio_method = getattr(_AioHealthCheckServicer, name)
                self.assertTrue(inspect.iscoroutinefunction(aio_method))
                self.assertIsNot(aio_method, getattr(_HealthCheckServicer, name))

    def test_every_sync_rpc_has_an_awaitable_counterpart(self):
        """A new RPC on the sync servicer must be mirrored as `async def` on the aio one."""
        rpc_names = self._rpc_names_for(
            (
                appcallback_service_v1.AppCallbackServicer,
                appcallback_service_v1.AppCallbackAlphaServicer,
            ),
            _CallbackServicer,
        )
        self.assertNotEqual([], rpc_names)

        for name in rpc_names:
            with self.subTest(rpc=name):
                aio_method = getattr(_AioCallbackServicer, name)
                self.assertTrue(
                    inspect.iscoroutinefunction(aio_method),
                    f'{name} must be a coroutine function on the asyncio servicer',
                )
                self.assertIsNot(
                    aio_method,
                    getattr(_CallbackServicer, name),
                    f'{name} must be overridden by the asyncio servicer, not inherited',
                )

    def test_registration_helpers_are_shared_not_duplicated(self):
        """Registration and routing must stay on the common base, not be reimplemented."""
        for name in ('register_method', 'register_topic', 'register_binding', 'register_job_event'):
            with self.subTest(helper=name):
                self.assertNotIn(name, vars(_AioCallbackServicer))
                self.assertIs(getattr(_AioCallbackServicer, name), getattr(_CallbackServicer, name))


if __name__ == '__main__':
    unittest.main()
