# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import base64
import json
import unittest
from datetime import timedelta

from google.protobuf import any_pb2, wrappers_pb2

from dapr.actor.error import (
    ActorMethodNotFoundError,
    ActorNotFoundError,
    ActorTypeNotFoundError,
)
from dapr.actor.runtime._grpc_callbacks import (
    build_initial_request,
    build_invoke_error_payload,
    build_reminder_fire_body,
    build_timer_fire_body,
    extract_reentrancy_id,
    status_code_for_exception,
)
from dapr.actor.runtime.config import (
    ActorReentrancyConfig,
    ActorRuntimeConfig,
    ActorTypeConfig,
)
from dapr.clients.exceptions import DaprInternalError
from dapr.proto import api_v1


def _packed_bytes_value(value: bytes) -> any_pb2.Any:
    packed = any_pb2.Any()
    packed.Pack(wrappers_pb2.BytesValue(value=value))
    return packed


class GrpcInitialRequestTests(unittest.TestCase):
    def test_default_config(self):
        config = ActorRuntimeConfig()
        config.update_entities(['DemoActor'])

        initial_request = build_initial_request(config)

        self.assertEqual(['DemoActor'], list(initial_request.entities))
        self.assertTrue(initial_request.HasField('actor_idle_timeout'))
        self.assertEqual(3600, initial_request.actor_idle_timeout.seconds)
        self.assertTrue(initial_request.HasField('drain_rebalanced_actors'))
        self.assertTrue(initial_request.drain_rebalanced_actors)
        self.assertFalse(initial_request.HasField('drain_ongoing_call_timeout'))
        self.assertFalse(initial_request.HasField('reentrancy'))
        self.assertEqual(0, len(initial_request.entities_config))

    def test_full_config(self):
        type_config = ActorTypeConfig(
            actor_type='ReentrantActor',
            actor_idle_timeout=timedelta(minutes=5),
            drain_ongoing_call_timeout=timedelta(seconds=15),
            drain_rebalanced_actors=False,
            reentrancy=ActorReentrancyConfig(enabled=True, maxStackDepth=8),
        )
        config = ActorRuntimeConfig(
            actor_idle_timeout=timedelta(minutes=30),
            drain_ongoing_call_timeout=timedelta(seconds=30),
            drain_rebalanced_actors=False,
            reentrancy=ActorReentrancyConfig(enabled=True),
            actor_type_configs=[type_config],
        )
        config.update_entities(['DemoActor'])

        initial_request = build_initial_request(config)

        self.assertEqual({'DemoActor', 'ReentrantActor'}, set(initial_request.entities))
        self.assertEqual(1800, initial_request.actor_idle_timeout.seconds)
        self.assertEqual(30, initial_request.drain_ongoing_call_timeout.seconds)
        self.assertFalse(initial_request.drain_rebalanced_actors)
        self.assertTrue(initial_request.reentrancy.enabled)
        self.assertEqual(32, initial_request.reentrancy.max_stack_depth)

        self.assertEqual(1, len(initial_request.entities_config))
        entity_config = initial_request.entities_config[0]
        self.assertEqual(['ReentrantActor'], list(entity_config.entities))
        self.assertEqual(300, entity_config.actor_idle_timeout.seconds)
        self.assertEqual(15, entity_config.drain_ongoing_call_timeout.seconds)
        self.assertTrue(entity_config.HasField('drain_rebalanced_actors'))
        self.assertFalse(entity_config.drain_rebalanced_actors)
        self.assertTrue(entity_config.reentrancy.enabled)
        self.assertEqual(8, entity_config.reentrancy.max_stack_depth)

    def test_unset_optionals_stay_unset(self):
        config = ActorRuntimeConfig(
            actor_idle_timeout=None,
            drain_rebalanced_actors=None,
        )

        initial_request = build_initial_request(config)

        self.assertFalse(initial_request.HasField('actor_idle_timeout'))
        self.assertFalse(initial_request.HasField('drain_rebalanced_actors'))


class ReentrancyIdExtractionTests(unittest.TestCase):
    def test_exact_header(self):
        metadata = {'Dapr-Reentrancy-Id': 'rid-1'}
        self.assertEqual('rid-1', extract_reentrancy_id(metadata))

    def test_case_insensitive(self):
        metadata = {'dapr-reentrancy-id': 'rid-2'}
        self.assertEqual('rid-2', extract_reentrancy_id(metadata))

    def test_missing(self):
        metadata = {'content-type': 'application/json'}
        self.assertIsNone(extract_reentrancy_id(metadata))


class ReminderFireBodyTests(unittest.TestCase):
    def test_with_base64_string_data(self):
        state = b'reminder_state'
        json_value = json.dumps(base64.b64encode(state).decode('utf-8')).encode('utf-8')
        reminder_request = api_v1.SubscribeActorEventsResponseReminderRequestAlpha1(
            id='1',
            actor_type='DemoActor',
            actor_id='a1',
            name='demo_reminder',
            due_time='0h0m5s',
            period='0h0m10s',
            data=_packed_bytes_value(json_value),
        )

        body = json.loads(build_reminder_fire_body(reminder_request))

        self.assertEqual(base64.b64encode(state).decode('utf-8'), body['data'])
        self.assertEqual(state, base64.b64decode(body['data']))

    def test_without_data(self):
        reminder_request = api_v1.SubscribeActorEventsResponseReminderRequestAlpha1(
            id='1', name='demo_reminder', due_time='5s', period='10s'
        )

        body = json.loads(build_reminder_fire_body(reminder_request))

        self.assertEqual('5s', body['dueTime'])
        self.assertEqual('10s', body['period'])
        self.assertNotIn('data', body)


class TimerFireBodyTests(unittest.TestCase):
    def _timer_request(self, data=None):
        timer_request = api_v1.SubscribeActorEventsResponseTimerRequestAlpha1(
            id='1',
            actor_type='DemoActor',
            actor_id='a1',
            name='demo_timer',
            due_time='5s',
            period='10s',
            callback='timer_callback',
            data=data,
        )
        return timer_request

    def test_http_registered_object_data(self):
        timer_request = self._timer_request(_packed_bytes_value(b'{"setting":1}'))

        body = json.loads(build_timer_fire_body(timer_request))

        self.assertEqual('timer_callback', body['callback'])
        self.assertEqual({'setting': 1}, body['data'])

    def test_grpc_registered_data_is_unwrapped(self):
        original_value = json.dumps({'setting': 1}).encode('utf-8')
        wrapped = json.dumps(base64.b64encode(original_value).decode('utf-8')).encode('utf-8')
        timer_request = self._timer_request(_packed_bytes_value(wrapped))

        body = json.loads(build_timer_fire_body(timer_request))

        self.assertEqual({'setting': 1}, body['data'])

    def test_plain_string_data_is_not_unwrapped(self):
        timer_request = self._timer_request(_packed_bytes_value(b'"not base64!"'))

        body = json.loads(build_timer_fire_body(timer_request))

        self.assertEqual('not base64!', body['data'])

    def test_without_data(self):
        timer_request = self._timer_request()

        body = json.loads(build_timer_fire_body(timer_request))

        self.assertIsNone(body['data'])

    def test_any_without_type_url_uses_raw_value(self):
        raw_any = any_pb2.Any(value=b'{"raw":true}')
        timer_request = self._timer_request(raw_any)

        body = json.loads(build_timer_fire_body(timer_request))

        self.assertEqual({'raw': True}, body['data'])

    def test_http_registered_base64_string_is_misdetected(self):
        """Documents the unwrap heuristic's known false positive: an
        HTTP-registered *string* payload that happens to be valid base64 of
        valid JSON is delivered decoded instead of as the original string."""
        inner_value = json.dumps({'key': 'value'}).encode('utf-8')
        ambiguous_string = base64.b64encode(inner_value).decode('utf-8')
        timer_request = self._timer_request(
            _packed_bytes_value(json.dumps(ambiguous_string).encode('utf-8'))
        )

        body = json.loads(build_timer_fire_body(timer_request))

        self.assertEqual({'key': 'value'}, body['data'])

    def test_invalid_json_data_raises_value_error(self):
        timer_request = self._timer_request(any_pb2.Any(value=b'\x00not json'))

        with self.assertRaises(ValueError) as raised:
            build_timer_fire_body(timer_request)
        self.assertIn('timer data is not valid JSON', str(raised.exception))


class InvokeErrorPayloadTests(unittest.TestCase):
    def test_dapr_internal_error(self):
        payload = json.loads(build_invoke_error_payload(DaprInternalError('boom', 'ERR_BOOM')))

        self.assertEqual('boom', payload['message'])
        self.assertEqual('ERR_BOOM', payload['errorCode'])

    def test_generic_exception(self):
        payload = json.loads(build_invoke_error_payload(RuntimeError('boom')))

        self.assertEqual("RuntimeError('boom')", payload['message'])
        self.assertEqual('UNKNOWN', payload['errorCode'])


class StatusCodeMappingTests(unittest.TestCase):
    def test_missing_actor_type_maps_to_not_found(self):
        error = ActorTypeNotFoundError('X is not registered.')
        self.assertEqual(5, status_code_for_exception(error))

    def test_unknown_method_maps_to_not_found(self):
        self.assertEqual(5, status_code_for_exception(ActorMethodNotFoundError('no method')))

    def test_value_error_maps_to_unknown(self):
        # A plain ValueError (e.g. invalid payload, non-remindable actor) is
        # retryable, not a permanent NOT_FOUND.
        self.assertEqual(2, status_code_for_exception(ValueError('bad payload')))

    def test_attribute_error_from_actor_code_maps_to_unknown(self):
        # Only the dispatcher's ActorMethodNotFoundError means "method does
        # not exist"; an AttributeError raised inside the actor's own code is
        # an application error.
        self.assertEqual(2, status_code_for_exception(AttributeError('user code bug')))

    def test_generic_exception_maps_to_unknown(self):
        self.assertEqual(2, status_code_for_exception(RuntimeError('boom')))


class ActorErrorPublicApiTests(unittest.TestCase):
    """Locks the actor errors as a public, catchable part of the SDK surface."""

    def test_errors_are_exported_from_dapr_actor(self):
        import dapr.actor as actor_pkg

        self.assertIs(actor_pkg.ActorNotFoundError, ActorNotFoundError)
        self.assertIs(actor_pkg.ActorMethodNotFoundError, ActorMethodNotFoundError)
        self.assertIs(actor_pkg.ActorTypeNotFoundError, ActorTypeNotFoundError)

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(ActorTypeNotFoundError, ActorNotFoundError))
        self.assertTrue(issubclass(ActorMethodNotFoundError, ActorNotFoundError))
        # Backwards compatible with code that caught the dispatcher's
        # historical bare AttributeError.
        self.assertTrue(issubclass(ActorMethodNotFoundError, AttributeError))


if __name__ == '__main__':
    unittest.main()
