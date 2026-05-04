import pytest

from dapr.clients.grpc.conversation import (
    ConversationInput,
    ConversationInputAlpha2,
    create_assistant_message,
    create_system_message,
    create_user_message,
)

COMPONENT = 'echo'


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-conversation')


def test_converse_alpha1_echoes_input(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[ConversationInput(content='sync hello', role='user')],
    )
    assert response.outputs[0].result == 'sync hello'


def test_converse_alpha1_with_multiple_inputs(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[
            ConversationInput(content='one', role='user'),
            ConversationInput(content='two', role='user'),
        ],
    )
    results = [out.result for out in response.outputs]
    # The echo component concatenates all inputs into a single newline-joined output
    # rather than echoing each input individually.
    assert results == ['one\ntwo']


def test_converse_alpha1_with_temperature(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[ConversationInput(content='warm', role='user')],
        temperature=0.7,
    )
    assert response.outputs[0].result == 'warm'


def test_converse_alpha2_echoes_user_message(client):
    response = client.converse_alpha2(
        name=COMPONENT,
        inputs=[ConversationInputAlpha2(messages=[create_user_message('sync world')])],
    )
    assert response.outputs[0].choices[0].message.content == 'sync world'


def test_converse_alpha2_with_mixed_messages(client):
    response = client.converse_alpha2(
        name=COMPONENT,
        inputs=[
            ConversationInputAlpha2(
                messages=[
                    create_system_message('be brief'),
                    create_user_message('hi'),
                    create_assistant_message('hello'),
                ]
            )
        ],
    )
    choice = response.outputs[0].choices[0]
    assert choice.message.content == 'be brief\nhi\nhello'
    assert choice.finish_reason == 'stop'
