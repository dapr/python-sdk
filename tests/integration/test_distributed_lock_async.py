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
from dapr.clients.grpc._response import UnlockResponseStatus

STORE = 'lockstore'
GRPC_ADDRESS = '127.0.0.1:13501'

# The distributed lock API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-lock-async')


async def test_acquire_and_release_lock(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        lock = await d.try_lock(STORE, 'res-async-acquire', 'owner-a', expiry_in_seconds=10)
        assert lock.success

        resp = await d.unlock(STORE, 'res-async-acquire', 'owner-a')
        assert resp.status == UnlockResponseStatus.success


async def test_second_owner_is_rejected(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        first = await d.try_lock(STORE, 'res-async-contention', 'owner-a', expiry_in_seconds=10)
        second = await d.try_lock(STORE, 'res-async-contention', 'owner-b', expiry_in_seconds=10)

    assert first.success
    assert not second.success


async def test_unlock_nonexistent_returns_not_found(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.unlock(STORE, 'res-async-missing', 'owner-a')

    assert resp.status == UnlockResponseStatus.lock_does_not_exist
