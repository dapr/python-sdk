import pytest

from dapr.clients.grpc.conversation import (
    ConversationInput,
    ConversationInputAlpha2,
    create_user_message,
)

COMPONENT = 'ollama'


@pytest.fixture(scope='module')
def client(dapr_env, ollama):
    return dapr_env.start_sidecar(app_id='test-conversation-ollama')


def test_converse_alpha1_returns_non_empty_response(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[
            ConversationInput(content='Reply with the single word: dapr', role='user'),
        ],
        temperature=0,
    )
    content = response.outputs[0].result.strip()
    assert 'dapr' in content


def test_converse_alpha2_answers_simple_arithmetic(client):
    response = client.converse_alpha2(
        name=COMPONENT,
        inputs=[
            ConversationInputAlpha2(
                messages=[create_user_message('What is 2 plus 2? Reply with only the number.')]
            )
        ],
        temperature=0,
    )
    content = response.outputs[0].choices[0].message.content
    assert '4' in content
