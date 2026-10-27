# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from dapr.aio.clients.grpc.interceptors import (
    DaprClientInterceptorAsync,
    _ClientCallDetailsAsync,
    _DaprStreamUnaryInterceptorAsync,
    _DaprUnaryStreamInterceptorAsync,
)
from dapr.clients.grpc.interceptors import DaprClientInterceptor, _ClientCallDetails


class DaprClientInterceptorTests(unittest.TestCase):
    def setUp(self):
        self._fake_request = 'fake request'

    def fake_continuation(self, call_details, request):
        return call_details

    def test_intercept_unary_unary_single_header(self):
        interceptor = DaprClientInterceptor([('api-token', 'test-token')])
        call_details = _ClientCallDetails('method1', 10, None, None, None, None)
        response = interceptor.intercept_unary_unary(
            self.fake_continuation, call_details, self._fake_request
        )

        self.assertIsNotNone(response)
        self.assertEqual(1, len(response.metadata))
        self.assertEqual([('api-token', 'test-token')], response.metadata)

    def test_intercept_unary_unary_existing_metadata(self):
        interceptor = DaprClientInterceptor([('api-token', 'test-token')])
        call_details = _ClientCallDetails('method1', 10, [('header', 'value')], None, None, None)
        response = interceptor.intercept_unary_unary(
            self.fake_continuation, call_details, self._fake_request
        )

        self.assertIsNotNone(response)
        self.assertEqual(2, len(response.metadata))
        self.assertEqual([('header', 'value'), ('api-token', 'test-token')], response.metadata)

    def test_api_token_precedence_preserves_other_metadata(self):
        interceptor = DaprClientInterceptor([('dapr-api-token', 'test-token')])
        for token in [None, 'test-token', 'caller-token', '']:
            metadata = [('header', 'first'), ('header', 'second')]
            if token is not None:
                metadata.append(('dapr-api-token', token))
            token_expected = 'test-token' if token is None else token
            metadata_expected = [*metadata[:2], ('dapr-api-token', token_expected)]
            call_details = _ClientCallDetails('method1', 10, metadata, None, None, None)
            for intercept in [
                interceptor.intercept_unary_unary,
                interceptor.intercept_unary_stream,
                interceptor.intercept_stream_unary,
                interceptor.intercept_stream_stream,
            ]:
                with self.subTest(intercept=intercept.__name__, token=token):
                    response = intercept(self.fake_continuation, call_details, self._fake_request)
                    self.assertEqual(metadata_expected, response.metadata)


class DaprClientInterceptorAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def fake_continuation(self, call_details, request):
        return call_details

    async def test_api_token_precedence_preserves_other_metadata(self):
        configured = [('dapr-api-token', 'test-token')]
        interceptor = DaprClientInterceptorAsync(configured)
        for token in [None, 'test-token', 'caller-token', '']:
            metadata = [('header', 'first'), ('header', 'second')]
            if token is not None:
                metadata.append(('dapr-api-token', token))
            token_expected = 'test-token' if token is None else token
            metadata_expected = [*metadata[:2], ('dapr-api-token', token_expected)]
            call_details = _ClientCallDetailsAsync('method1', 10, metadata, None, None)
            for intercept in [
                interceptor.intercept_unary_unary,
                interceptor.intercept_stream_stream,
                _DaprUnaryStreamInterceptorAsync(configured).intercept_unary_stream,
                _DaprStreamUnaryInterceptorAsync(configured).intercept_stream_unary,
            ]:
                with self.subTest(intercept=intercept.__name__, token=token):
                    response = await intercept(self.fake_continuation, call_details, 'fake request')
                    self.assertEqual(metadata_expected, response.metadata)
