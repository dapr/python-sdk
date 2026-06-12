# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import sys
from unittest.mock import patch

from dapr.ext.workflow._durabletask.aio.internal import shared

HOST_ADDRESS = 'localhost:50051'


def _record(msg: str, exc: BaseException | None) -> logging.LogRecord:
    exc_info = None
    if exc is not None:
        try:
            raise exc
        except BaseException:
            exc_info = sys.exc_info()
    return logging.LogRecord('asyncio', logging.ERROR, __file__, 1, msg, (), exc_info)


def test_filter_drops_poller_eagain_record():
    record = _record(
        'Exception in callback PollerCompletionQueue._handle_events()',
        BlockingIOError(11, 'Resource temporarily unavailable'),
    )
    assert shared._GrpcAioPollerNoiseFilter().filter(record) is False


def test_filter_keeps_record_without_exception():
    assert shared._GrpcAioPollerNoiseFilter().filter(_record('some other error', None)) is True


def test_filter_keeps_blockingioerror_without_marker():
    record = _record('unrelated message', BlockingIOError(11, 'nope'))
    assert shared._GrpcAioPollerNoiseFilter().filter(record) is True


def test_get_grpc_aio_channel_installs_filter_on_asyncio_logger():
    asyncio_logger = logging.getLogger('asyncio')
    for existing in [
        f for f in asyncio_logger.filters if isinstance(f, shared._GrpcAioPollerNoiseFilter)
    ]:
        asyncio_logger.removeFilter(existing)

    with patch('dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'):
        shared.get_grpc_aio_channel(HOST_ADDRESS, False)

    installed = [
        f for f in asyncio_logger.filters if isinstance(f, shared._GrpcAioPollerNoiseFilter)
    ]
    assert len(installed) == 1  # installed once, not duplicated


def test_install_is_idempotent():
    asyncio_logger = logging.getLogger('asyncio')
    shared._silence_grpc_aio_poller_noise()
    shared._silence_grpc_aio_poller_noise()
    installed = [
        f for f in asyncio_logger.filters if isinstance(f, shared._GrpcAioPollerNoiseFilter)
    ]
    assert len(installed) == 1
