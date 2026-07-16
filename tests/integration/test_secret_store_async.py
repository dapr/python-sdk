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

STORE = 'localsecretstore'
GRPC_ADDRESS = '127.0.0.1:13501'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-secrets-async')


async def test_get_secret_returns_expected_value(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.get_secret(store_name=STORE, key='secretKey')

    assert resp.secret == {'secretKey': 'secretValue'}


async def test_get_bulk_secret_returns_all(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.get_bulk_secret(store_name=STORE)

    assert 'secretKey' in resp.secrets
    assert resp.secrets['secretKey'] == {'secretKey': 'secretValue'}
