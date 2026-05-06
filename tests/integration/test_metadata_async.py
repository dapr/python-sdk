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

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient

GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-metadata-async')


async def test_get_metadata_application_id_matches(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        meta = await d.get_metadata()

    assert meta.application_id == 'test-metadata-async'


async def test_set_and_get_metadata_round_trip(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.set_metadata('async-key', 'async-value')
        meta = await d.get_metadata()

    assert meta.extended_metadata.get('async-key') == 'async-value'
