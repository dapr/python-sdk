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
from unittest.mock import patch

from dapr.common.logging import GrpcAioPollerNoiseFilter
from dapr.ext.workflow._durabletask.aio.internal import shared

HOST_ADDRESS = 'localhost:50051'


def test_get_grpc_aio_channel_installs_filter_on_asyncio_logger():
    """Filter behavior itself is covered in tests/common/test_logging.py."""
    asyncio_logger = logging.getLogger('asyncio')
    for existing in [f for f in asyncio_logger.filters if isinstance(f, GrpcAioPollerNoiseFilter)]:
        asyncio_logger.removeFilter(existing)

    with patch('dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'):
        shared.get_grpc_aio_channel(HOST_ADDRESS, False)

    installed = [f for f in asyncio_logger.filters if isinstance(f, GrpcAioPollerNoiseFilter)]
    assert len(installed) == 1  # installed once, not duplicated
