# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from cloudevents.sdk.event import v1
from dapr.ext.grpc import App, InvokeServiceRequest, BindingRequest


class AppTests(unittest.TestCase):
    def setUp(self):
        self._app = App()

    def test_method_decorator(self):
        @self._app.method('Method1')
        def method1(request: InvokeServiceRequest):
            pass

        @self._app.method('Method2')
        def method2(request: InvokeServiceRequest):
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
            'AppTests.test_binding_decorator.<locals>.binding1',
            str(binding_map['binding1']))

    def test_subscribe_decorator(self):
        @self._app.subscribe(topic='topic')
        def topic(event: v1.Event) -> None:
            pass

        subscription_map = self._app._servicer._topic_map
        self.assertIn(
            'AppTests.test_subscribe_decorator.<locals>.topic',
            str(subscription_map['topic']))
