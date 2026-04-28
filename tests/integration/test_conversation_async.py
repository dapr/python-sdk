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
