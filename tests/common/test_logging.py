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

import logging
import sys
import unittest

from dapr.common.logging import GrpcAioPollerNoiseFilter, silence_grpc_aio_poller_noise


def _error_record(msg: str, exc: BaseException | None) -> logging.LogRecord:
    exc_info = None
    if exc is not None:
        try:
            raise exc
        except BaseException:
            exc_info = sys.exc_info()
    return logging.LogRecord('asyncio', logging.ERROR, __file__, 1, msg, (), exc_info)


class TestGrpcAioPollerNoiseFilter(unittest.TestCase):
    def tearDown(self):
        asyncio_logger = logging.getLogger('asyncio')
        for existing in list(asyncio_logger.filters):
            if isinstance(existing, GrpcAioPollerNoiseFilter):
                asyncio_logger.removeFilter(existing)

    def test_filter_drops_poller_eagain_record(self):
        record = _error_record(
            'Exception in callback PollerCompletionQueue._handle_events()',
            BlockingIOError(11, 'Resource temporarily unavailable'),
        )
        self.assertFalse(GrpcAioPollerNoiseFilter().filter(record))

    def test_filter_keeps_record_without_exception(self):
        record = _error_record('some other error', None)
        self.assertTrue(GrpcAioPollerNoiseFilter().filter(record))

    def test_filter_keeps_blockingioerror_without_marker(self):
        record = _error_record('unrelated message', BlockingIOError(11, 'nope'))
        self.assertTrue(GrpcAioPollerNoiseFilter().filter(record))

    def test_install_is_idempotent(self):
        silence_grpc_aio_poller_noise()
        silence_grpc_aio_poller_noise()
        asyncio_logger = logging.getLogger('asyncio')
        installed = [f for f in asyncio_logger.filters if isinstance(f, GrpcAioPollerNoiseFilter)]
        self.assertEqual(len(installed), 1)
