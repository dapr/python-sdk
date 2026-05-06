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
from dapr.clients.grpc.conversation import (
    ConversationInput,
    ConversationInputAlpha2,
    create_user_message,
)

COMPONENT = 'echo'
GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-conversation-async')


async def test_converse_alpha1_echoes_input(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        response = await d.converse_alpha1(
            name=COMPONENT,
            inputs=[ConversationInput(content='async hello', role='user')],
        )

    assert response.outputs[0].result == 'async hello'


async def test_converse_alpha2_echoes_user_message(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        response = await d.converse_alpha2(
            name=COMPONENT,
            inputs=[ConversationInputAlpha2(messages=[create_user_message('async world')])],
        )

    assert response.outputs[0].choices[0].message.content == 'async world'
