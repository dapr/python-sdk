# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

import unittest

from cloudevents.sdk.event import v1
from dapr.ext.grpc import App, Rule, InvokeMethodRequest, BindingRequest


class AppTests(unittest.TestCase):
    def setUp(self):
        self._app = App()

    def test_method_decorator(self):
        @self._app.method('Method1')
        def method1(request: InvokeMethodRequest):
            pass

        @self._app.method('Method2')
        def method2(request: InvokeMethodRequest):
            pass

        method_map = self._app._servicer._invoke_method_map
        self.assertIn('AppTests.test_method_decorator.<locals>.method1', str(method_map['Method1']))
        self.assertIn('AppTests.test_method_decorator.<locals>.method2', str(method_map['Method2']))

    def test_binding_decorator(self):
        @self._app.binding('binding1')
        def binding1(request: BindingRequest):
            pass

        binding_map = self._app._servicer._binding_map
        self.assertIn(
            'AppTests.test_binding_decorator.<locals>.binding1', str(binding_map['binding1'])
        )

    def test_subscribe_decorator(self):
        @self._app.subscribe(pubsub_name='pubsub', topic='topic')
        def handle_default(event: v1.Event) -> None:
            pass

        @self._app.subscribe(
            pubsub_name='pubsub', topic='topic', rule=Rule('event.type == "test"', 1)
        )
        def handle_test_event(event: v1.Event) -> None:
            pass

        @self._app.subscribe(pubsub_name='pubsub', topic='topic2', dead_letter_topic='topic2_dead')
        def handle_dead_letter(event: v1.Event) -> None:
            pass

        subscription_map = self._app._servicer._topic_map
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.handle_default',
            str(subscription_map['pubsub:topic:']),
        )
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.handle_test_event',
            str(subscription_map['pubsub:topic:handle_test_event']),
        )
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.handle_dead_letter',
            str(subscription_map['pubsub:topic2:']),
        )

    def test_register_health_check(self):
        def health_check_cb():
            pass

        self._app.register_health_check(health_check_cb)
        registered_cb = self._app._health_check_servicer._health_check_cb
        self.assertIn(
            'AppTests.test_register_health_check.<locals>.health_check_cb', str(registered_cb)
        )

    def test_no_health_check(self):
        registered_cb = self._app._health_check_servicer._health_check_cb
        self.assertIsNone(registered_cb)
