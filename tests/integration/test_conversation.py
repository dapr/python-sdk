import pytest

from dapr.clients.grpc.conversation import (
    ConversationInput,
    ConversationInputAlpha2,
    ConversationTools,
    ConversationToolsFunction,
    create_user_message,
)

COMPONENT = 'echo'


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-conversation')


def test_alpha1_single_input_is_echoed(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[ConversationInput(content='hello world', role='user')],
    )

    assert len(response.outputs) == 1
    assert response.outputs[0].result == 'hello world'


def test_alpha1_multiple_inputs_are_joined_by_echo(client):
    messages = ['first', 'second', 'third']
    inputs = [ConversationInput(content=text, role='user') for text in messages]

    response = client.converse_alpha1(name=COMPONENT, inputs=inputs)

    assert len(response.outputs) == 1
    assert response.outputs[0].result == '\n'.join(messages)


def test_alpha1_context_id_is_echoed(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[ConversationInput(content='ping', role='user')],
        context_id='chat-123',
    )

    assert response.context_id == 'chat-123'


def test_alpha1_temperature_and_scrub_pii_are_accepted(client):
    response = client.converse_alpha1(
        name=COMPONENT,
        inputs=[ConversationInput(content='hi', role='user', scrub_pii=True)],
        temperature=0.7,
        scrub_pii=True,
    )

    assert response.outputs[0].result == 'hi'


def test_alpha2_user_message_is_echoed(client):
    response = client.converse_alpha2(
        name=COMPONENT,
        inputs=[ConversationInputAlpha2(messages=[create_user_message("What's Dapr?")])],
    )

    assert len(response.outputs) == 1
    assert len(response.outputs[0].choices) == 1
    assert response.outputs[0].choices[0].message.content == "What's Dapr?"


def test_alpha2_multiple_inputs_are_joined_by_echo(client):
    prompts = ['one', 'two']
    inputs = [ConversationInputAlpha2(messages=[create_user_message(text)]) for text in prompts]

    response = client.converse_alpha2(name=COMPONENT, inputs=inputs)

    assert len(response.outputs) == 1
    assert response.outputs[0].choices[0].message.content == '\n'.join(prompts)


def test_alpha2_tools_and_tool_choice_are_accepted(client):
    weather_tool = ConversationTools(
        function=ConversationToolsFunction(
            name='get_weather',
            description='Look up the weather for a city',
            parameters={
                'type': 'object',
                'properties': {'city': {'type': 'string'}},
                'required': ['city'],
            },
        ),
    )

    response = client.converse_alpha2(
        name=COMPONENT,
        inputs=[ConversationInputAlpha2(messages=[create_user_message('weather in Paris?')])],
        tools=[weather_tool],
        tool_choice='auto',
    )

    assert response.outputs[0].choices[0].message.content == 'weather in Paris?'


def test_alpha2_parameters_and_metadata_are_accepted(client):
    response = client.converse_alpha2(
        name=COMPONENT,
        inputs=[ConversationInputAlpha2(messages=[create_user_message('hi')])],
        parameters={'top_p': 0.9, 'max_tokens': 64},
        metadata={'model': 'echo', 'cacheTTL': '1m'},
        context_id='ctx-xyz',
    )

    assert response.context_id == 'ctx-xyz'
    assert response.outputs[0].choices[0].message.content == 'hi'
