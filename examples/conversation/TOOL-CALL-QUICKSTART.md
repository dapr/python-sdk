# Conversation API Tool Calling Quickstart (Alpha2)

This guide shows the cleanest, most ergonomic way to use the Conversation API with tools and multi‑turn flows.

## Recommended: Decorator‑based Tools

```python
from dapr.clients import DaprClient
from dapr.clients.grpc import conversation


@conversation.tool
def get_weather(location: str, unit: str = 'fahrenheit') -> str:
    """Get current weather for a location."""
    return f"Weather in {location} (unit={unit})"


user_msg = conversation.create_user_message("What's the weather in Paris?")
input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_msg])

with DaprClient() as client:
    response = client.converse_alpha2(
        name="openai",
        inputs=[input_alpha2],
        tools=conversation.get_registered_tools(),  # tools registered by @conversation.tool
        tool_choice='auto',
        parameters={'temperature': 0.2, 'max_tokens': 200},  # raw values auto-converted
    )

    for msg in response.to_assistant_messages():
        if msg.of_assistant.tool_calls:
            for tc in msg.of_assistant.tool_calls:
                print(f"Tool call: {tc.function.name} args={tc.function.arguments}")
        else:
            print(msg.of_assistant.content[0].text)
```

## Minimal Multi‑turn Pattern with Tools

```python
from dapr.clients import DaprClient
from dapr.clients.grpc import conversation


@conversation.tool
def get_weather(location: str, unit: str = 'fahrenheit') -> str:
    return f"Weather in {location} (unit={unit})"


history: list[conversation.ConversationMessage] = []
history.append(conversation.create_user_message("What's the weather in San Francisco?"))

with DaprClient() as client:
    # Turn 1
    resp1 = client.converse_alpha2(
        name="openai",
        inputs=[conversation.ConversationInputAlpha2(messages=history)],
        tools=conversation.get_registered_tools(),
        tool_choice='auto',
        parameters={'temperature': 0.2},
    )

    # Append assistant messages; execute any tool calls and append tool results
    for msg in resp1.to_assistant_messages():
        history.append(msg)
        for tc in msg.of_assistant.tool_calls:
            # Execute (we suggest validating inputs before execution in production)
            tool_output = conversation.execute_registered_tool(tc.function.name, tc.function.arguments)
            history.append(
                conversation.create_tool_message(tool_id=tc.id, name=tc.function.name, content=str(tool_output))
            )

    # Turn 2 (LLM sees tool result)
    history.append(conversation.create_user_message("Should I bring an umbrella?"))
    resp2 = client.converse_alpha2(
        name="openai",
        inputs=[conversation.ConversationInputAlpha2(messages=history)],
        tools=conversation.get_registered_tools(),
        parameters={'temperature': 0.2},
    )

    for msg in resp2.to_assistant_messages():
        history.append(msg)
        if not msg.of_assistant.tool_calls:
            print(msg.of_assistant.content[0].text)
```

 

## Alternative: Function‑to‑Schema (from_function)

```python
from enum import Enum
from dapr.clients.grpc import conversation


class Units(Enum):
    CELSIUS = 'celsius'
    FAHRENHEIT = 'fahrenheit'


def get_weather(location: str, unit: Units = Units.FAHRENHEIT) -> str:
    return f"Weather in {location}"


fn = conversation.ConversationToolsFunction.from_function(get_weather)
weather_tool = conversation.ConversationTools(function=fn)
```

## JSON Schema Variants (fallbacks)

```python
from dapr.clients.grpc import conversation


# Simple schema
fn = conversation.ConversationToolsFunction(
    name='get_weather',
    description='Get current weather',
    parameters={
        'type': 'object',
        'properties': {
            'location': {'type': 'string'},
            'unit': {'type': 'string', 'enum': ['celsius', 'fahrenheit']},
        },
        'required': ['location'],
    },
)
weather_tool = conversation.ConversationTools(function=fn)
```

## Async Variant

```python
import asyncio
from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients.grpc import conversation


@conversation.tool
def get_time() -> str:
    return '2025-01-01T12:00:00Z'


async def main():
    async with AsyncDaprClient() as client:
        msg = conversation.create_user_message('What time is it?')
        inp = conversation.ConversationInputAlpha2(messages=[msg])
        resp = await client.converse_alpha2(
            name='openai', inputs=[inp], tools=conversation.get_registered_tools()
        )
        for m in resp.to_assistant_messages():
            if m.of_assistant.content:
                print(m.of_assistant.content[0].text)


asyncio.run(main())
```

## See also

- `examples/conversation/real_llm_providers_example.py` — end‑to‑end multi‑turn and tool calling flows with real providers
- Main README in this folder for provider setup and additional examples


