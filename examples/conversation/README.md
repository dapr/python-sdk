# Dapr Python SDK - Conversation API Examples

This directory contains examples demonstrating how to use the Dapr Conversation API with the Python SDK, including real LLM provider integrations and advanced Alpha2 features.

## Real LLM Providers Support

The Conversation API supports real LLM providers including:

- **OpenAI** (GPT-4o-mini, GPT-4, etc.)
- **Anthropic** (Claude Sonnet 4, Claude Haiku, etc.)
- **Mistral** (Mistral Large, etc.)
- **DeepSeek** (DeepSeek V3, etc.)
- **Google AI** (Gemini 2.5 Flash, etc.)

### Environment Setup

1. **Install dependencies:**
   ```bash
   pip install python-dotenv  # For .env file support
   ```

2. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

3. **Add your API keys to .env:**
   ```bash
   OPENAI_API_KEY=your_openai_key_here
   ANTHROPIC_API_KEY=your_anthropic_key_here
   MISTRAL_API_KEY=your_mistral_key_here
   DEEPSEEK_API_KEY=your_deepseek_key_here
   GOOGLE_API_KEY=your_google_ai_key_here
   ```
   
4. **Run the simple conversation on the Alpha V1 version (dapr 1.15)**
    <!-- STEP
    name: Run Conversation Alpha V1
    expected_stdout_lines:
      - "== APP == Result: What's Dapr?"
      - "== APP == Give a brief overview."
    background: true
    timeout_seconds: 60
    -->
    
    ```bash
    dapr run --app-id conversation-alpha1 \
             --log-level debug \
             --resources-path ./config \
             -- python3 conversation_alpha1.py
    ```
    
    <!-- END_STEP -->

5. **Run the simple conversation on the Alpha V2 version (dapr 1.16)**
    <!-- STEP
    name: Run Conversation Alpha V2
    expected_stdout_lines:
      - "== APP == Result: What's Dapr?"
      - "== APP == Give a brief overview."
    background: true
    timeout_seconds: 60
    -->
    
    ```bash
    dapr run --app-id conversation-alpha2 \
             --log-level debug \
             --resources-path ./config \
             -- python3 conversation_alpha2.py
    ```
    
    <!-- END_STEP -->

6. **Run the comprehensive example with real LLM providers (This requires LLMAPI Keys)**

   ```bash
   python examples/conversation/real_llm_providers_example.py
   ```

   Depending on what API key you have, this will run and print the result of each test function in the example file.

   Before running the example, you need to start the Dapr sidecar with the component configurations as shown below in our run output.
   Here we have a temporary directory with the component configurations with the API keys setup in the .env file.

   ```bash
   dapr run --app-id test-app --dapr-http-port 3500 --dapr-grpc-port 50001 --resources-path <some temporary directory>
   ```

   For example if we have openai, anthropic, mistral, deepseek and google ai, we will have a temporary directory with the component configurations for each provider:

   The example will run and print the result of each test function in the example file.
   ```bash
    🚀 Real LLM Providers Example for Dapr Conversation API Alpha2
    ============================================================
    📁 Loaded environment from /Users/filinto/diagrid/python-sdk/examples/conversation/.env

    🔍 Detecting available LLM providers...

    ✅ Found 5 configured provider(s)
    📝 Created component: /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3/openai.yaml
    📝 Created component: /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3/anthropic.yaml
    📝 Created component: /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3/mistral.yaml
    📝 Created component: /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3/deepseek.yaml
    📝 Created component: /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3/google.yaml

    ⚠️  IMPORTANT: Make sure Dapr sidecar is running with components from:
    /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3

    To start the sidecar with these components:
    dapr run --app-id test-app --dapr-http-port 3500 --dapr-grpc-port 50001 --resources-path /var/folders/3t/b6jkjnv970l6dd1sp81b19hw0000gn/T/dapr-llm-components-9mcpb1a3

    Press Enter when Dapr sidecar is running with the component configurations...
    ```

    At this point, you can press Enter to continue if you have the Dapr sidecar running with the component configurations.

## Alpha2 API Features

The Alpha2 API introduces sophisticated features:

- **Advanced Message Types**: user, system, assistant, developer, tool messages
- **Automatic Parameter Conversion**: Raw Python values → GrpcAny
- **Tool Calling**: Function calling with JSON schema definition
- **Function-to-Schema**: Ultimate DevEx for tool creation
- **Multi-turn Conversations**: Context accumulation across turns
- **Async Support**: Full async/await implementation

## Current Limitations

- **Streaming**: Response streaming is not yet supported in Alpha2. All responses are returned as complete messages.

## Tool Creation (Alpha2) - Excellent DevEx!

The Alpha2 API provides powerful functions for tool creation and parameter handling with clean JSON schema support.
You can either define tools via JSON schema or use the recommended decorator-based approach that auto-generates the schema from a typed Python function.

### Decorator-based Tool Definition (Recommended for most use cases)
```python
from dapr.clients.grpc import conversation

@conversation.tool
def get_weather(location: str, unit: str = 'fahrenheit') -> str:
    """Get current weather for a location."""
    # Implementation or placeholder
    return f"Weather in {location} (unit={unit})"

# Tools registered via @conversation.tool can be retrieved with:
tools = conversation.get_registered_tools()
```

### Simple JSON Schema Approach
```python
# Clean, simple, intuitive approach using standard JSON schema
from dapr.clients.grpc import conversation

function = conversation.ConversationToolsFunction(
    name="get_weather",
    description="Get current weather",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string", 
                "description": "City name"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"]
            }
        },
        "required": ["location"]
    }
)
weather_tool = conversation.ConversationTools(function=function)
```

### Automatic Parameter Conversion

Parameters argument in the converse method for alpha2 are now automatically converted from raw Python types:

```python
# Before: Manual GrpcAny creation for every parameter ❌
temp_param = GrpcAny()
temp_param.Pack(DoubleValue(value=0.7))

# After: Raw Python values automatically converted ✅
response = client.converse_alpha2(
    name="my-provider",
    inputs=[input_alpha2],
    parameters={
        'temperature': 0.7,          # float -> GrpcAny
        'max_tokens': 1000,          # int -> GrpcAny
        'stream': False,             # bool -> GrpcAny
        'model': 'gpt-4',            # string -> GrpcAny
        'config': {                  # dict -> GrpcAny (JSON)
            'features': ['a', 'b'],  # nested arrays supported
            'enabled': True          # nested values converted
        }
    }
)
```


### Alternative: Function-to-Schema (from_function)

We provide a helper function to automatically generate the tool schema from a Python function.

```python
from enum import Enum
from dapr.clients.grpc import conversation


class Units(Enum):
    CELSIUS = 'celsius'
    FAHRENHEIT = 'fahrenheit'


def get_weather(location: str, unit: Units = Units.FAHRENHEIT) -> str:
    """Get current weather for a location."""
    return f"Weather in {location}"


# Use the from_function class method for automatic schema generation
function = conversation.ConversationToolsFunction.from_function(get_weather)
weather_tool = conversation.ConversationTools(function=function)
```

**Benefits:**
- ✅ **Type Safety**: Full Python type hint support (str, int, List, Optional, Enum, etc.)
- ✅ **Auto-Documentation**: Docstring parsing for parameter descriptions
- ✅ **Ultimate DevEx**: Define functions, get tools automatically
- ✅ **90%+ less boilerplate** compared to manual schema creation

### Alternative Tool Creation Approaches

If you can't use the decorator (e.g., dynamic registration), these alternatives mirror the same
schema but require a bit more boilerplate.

#### 1) Simple JSON Schema
```python
from dapr.clients.grpc import conversation

function = conversation.ConversationToolsFunction(
    name="get_weather",
    description="Get weather",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        },
        "required": ["location"]
    }
)
weather_tool = conversation.ConversationTools(function=function)
```

#### 2) Complete JSON Schema
```python
from dapr.clients.grpc import conversation

function = conversation.ConversationToolsFunction(
    name="calculate", 
    description="Perform calculations",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression"}
        },
        "required": ["expression"]
    }
)
calc_tool = conversation.ConversationTools(function=function)
```

#### 3) No Parameters
```python
from dapr.clients.grpc import conversation

function = conversation.ConversationToolsFunction(
    name="get_time",
    description="Get current time",
    parameters={"type": "object", "properties": {}, "required": []}
)
time_tool = conversation.ConversationTools(function=function)
```

#### 4) Complex Schema with Arrays
```python
from dapr.clients.grpc import conversation

function = conversation.ConversationToolsFunction(
    name="search",
    description="Search the web", 
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "domains": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["query"]
    }
)
search_tool = conversation.ConversationTools(function=function)
```

## Advanced Message Types (Alpha2)

Alpha2 supports sophisticated message structures for complex conversations:

### User Messages

```python

from dapr.clients.grpc._conversation import ConversationMessageContent, ConversationMessageOfDeveloper,

ConversationMessage
ConversationMessageOfTool
ConversationMessageOfAssistant
ConversationMessageOfUser
ConversationMessageOfSystem

user_message = ConversationMessage(
    of_user=ConversationMessageOfUser(
        content=[ConversationMessageContent(text="What's the weather in Paris?")]
    )
)
```

### System Messages
```python
system_message = ConversationMessage(
    of_system=ConversationMessageOfSystem(
        content=[ConversationMessageContent(text="You are a helpful AI assistant.")]
    )
)
```

### Developer Messages
```python
developer_message = ConversationMessage(
    of_developer=ConversationMessageOfDeveloper(
        name="developer",
        content=[ConversationMessageContent(text="System configuration update.")]
    )
)
```

### Assistant Messages
```python
assistant_message = ConversationMessage(
    of_assistant=ConversationMessageOfAssistant(
        content=[ConversationMessageContent(text="I can help you with that!")],
        tool_calls=[...]  # Optional tool calls
    )
)
```

### Tool Messages (for tool responses)
```python
tool_message = ConversationMessage(
    of_tool=ConversationMessageOfTool(
        tool_id="call_123",
        name="get_weather",
        content=[ConversationMessageContent(text="Weather: 72°F, sunny")]
    )
)
```

## Multi-turn Conversations

Alpha2 excels at multi-turn conversations with proper context accumulation:

```python
from dapr.clients.grpc import conversation
from dapr.clients.grpc._response import ConversationResultAlpha2

conversation_history: list[conversation.ConversationMessage] = []

# Turn 1: User asks question
conversation_history.append(conversation.create_user_message("What's the weather in SF?"))

response1: ConversationResultAlpha2 = client.converse_alpha2(
    name="openai",
    inputs=[conversation.ConversationInputAlpha2(messages=conversation_history)],
    tools=conversation.get_registered_tools(),
    tool_choice='auto',
)

# Append assistant messages directly using the helper
for msg in response1.to_assistant_messages():
    conversation_history.append(msg)
    # If tool calls were returned, you can execute and append a tool message
    for tc in msg.of_assistant.tool_calls:
        tool_output = conversation.execute_registered_tool(tc.function.name, tc.function.arguments)
        conversation_history.append(
            conversation.create_tool_message(tool_id=tc.id, name=tc.function.name, content=str(tool_output))
        )

# Turn 2 with accumulated context
conversation_history.append(conversation.create_user_message("Should I bring an umbrella?"))
response2 = client.converse_alpha2(
    name="openai",
    inputs=[conversation.ConversationInputAlpha2(messages=conversation_history)],
    tools=conversation.get_registered_tools(),
)
```

### Trace print

We have added a trace print method to the ConversationMessage class that will print the conversation history with the direction arrows and the content of the messages that is good for debugging.

For example in the real_llm_providers_example.py file, we have the following code in a multi-turn conversation:

```python

    for msg in conversation_history:
        msg.trace_print(2)
```

That will print the conversation history with the following output (might vary depending on the LLM provider):

```
Full conversation history trace:

  client[user]      ---------> LLM[assistant]:
    content[0]: What's the weather like in San Francisco? Use one of the tools available.

  client            <-------- LLM[assistant]:
    tool_calls: 1
      [0] id=call_23YKsQyzRhQxcNjjRNRhMmze function=get_weather({"location":"San Francisco"})

  client[tool]      --------> LLM[assistant]:
    tool_id: call_23YKsQyzRhQxcNjjRNRhMmze
    name: get_weather
    content[0]: The weather in San Francisco is sunny with a temperature of 72°F.

  client            <-------- LLM[assistant]:
    content[0]: The weather in San Francisco is sunny with a temperature of 72°F.

  client[user]      ---------> LLM[assistant]:
    content[0]: Should I bring an umbrella? Also, what about the weather in New York?

  client            <-------- LLM[assistant]:
    tool_calls: 2
      [0] id=call_eWXkLbxKOAZRPoaAK0siYwHx function=get_weather({"location": "New York"})
      [1] id=call_CnKVzPmbCUEPZqipoemMF5jr function=get_weather({"location": "San Francisco"})

  client[tool]      --------> LLM[assistant]:
    tool_id: call_eWXkLbxKOAZRPoaAK0siYwHx
    name: get_weather
    content[0]: The weather in New York is sunny with a temperature of 72°F.

  client[tool]      --------> LLM[assistant]:
    tool_id: call_CnKVzPmbCUEPZqipoemMF5jr
    name: get_weather
    content[0]: The weather in San Francisco is sunny with a temperature of 72°F.

  client            <-------- LLM[assistant]:
    content[0]: The weather in both San Francisco and New York is sunny with a temperature of 72°F. Since it's sunny in both locations, you likely won't need to bring an umbrella.
```


### How context accumulation works

- Context is not automatic. Each turn you must pass the entire `messages` history you want the LLM to see.
- Append assistant responses using `response.to_assistant_messages()` before the next turn.
- If the LLM makes tool calls, execute them locally and append a tool result message via `conversation.create_tool_message(...)`.
- Re-send available tools on every turn (e.g., `tools=conversation.get_registered_tools()`), especially when the provider requires tools to be present to call them.
- Keep history as a list of `ConversationMessage` objects; add new user/assistant/tool messages as the dialog progresses.
- Context Engineering is a key skill for multi-turn conversations and you will need to experiment with different approaches to get the best results as you cannot keep accumulating context forever.

## Async Support

Full async/await support for non-blocking operations:

```python
from dapr.aio.clients import DaprClient as AsyncDaprClient

async def async_conversation():
    async with AsyncDaprClient() as client:
        user_message = create_user_message("Tell me a joke about async programming.")
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])
        
        response = await client.converse_alpha2(
            name="openai",
            inputs=[input_alpha2],
            parameters={'temperature': 0.7}
        )
        
        return response.outputs[0].choices[0].message.content

# Run async function
result = asyncio.run(async_conversation())
```

## Benefits

- ✅ **Clean JSON schema definition**
- ✅ **Automatic type conversion**
- ✅ **Multiple input formats supported**
- ✅ **Direct Python dict to protobuf Struct conversion**
- ✅ **Clean, readable code**
- ✅ **Supports complex nested structures**
- ✅ **Real LLM provider integration**
- ✅ **Multi-turn conversation support**
- ✅ **Function-to-schema automation**
- ✅ **Full async/await support**

## Dapr Component Configuration

For real LLM providers, you need Dapr component configurations. The example automatically creates these:

### OpenAI Component Example
```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: openai
spec:
  type: conversation.openai
  version: v1
  metadata:
    - name: key
      value: "your_openai_api_key"
    - name: model
      value: "gpt-4o-mini"
```

### Running with Dapr Sidecar
```bash
# The example creates temporary component configs and shows you the command:
dapr run --app-id test-app --dapr-http-port 3500 --dapr-grpc-port 50001 --resources-path /tmp/dapr-llm-components-xyz/
```

## Helper Functions

Convert LLM responses for multi-turn conversations:

```python
from dapr.clients.grpc._response import ConversationResultAlpha2Message


def convert_llm_response_to_conversation_message(
        result_message: ConversationResultAlpha2Message) -> ConversationMessage:
    """Convert ConversationResultMessage (from LLM response) to ConversationMessage (for conversation input)."""
    content = []
    if result_message.content:
        content = [ConversationMessageContent(text=result_message.content)]

    tool_calls = result_message.tool_calls or []

    return ConversationMessage(
        of_assistant=ConversationMessageOfAssistant(
            content=content,
            tool_calls=tool_calls
        )
    )


# Usage in multi-turn conversations
response = client.converse_alpha2(name="openai", inputs=[input_alpha2], tools=[tool])
choice = response.outputs[0].choices[0]
assistant_message = convert_llm_response_to_conversation_message(choice.message)
conversation_history.append(assistant_message)
```

## Examples in This Directory

- **`real_llm_providers_example.py`** - Comprehensive Alpha2 examples with real providers
  - Real LLM provider setup (OpenAI, Anthropic, Mistral, DeepSeek, Google AI)
  - Basic conversation testing (Alpha2)
  - Multi-turn conversation testing
  - Tool calling with real LLMs
  - Parameter conversion demonstration  
  - Multi-turn tool calling with context accumulation
  - Function-to-schema automatic tool generation
  - Decorator-based tool definition
  - Async conversation and tool calling support
  - Backward compatibility with Alpha1

- **`conversation_alpha1.py`** - Basic conversation examples (Alpha1)
  - Simple Alpha1 conversation flow
- **`conversation_alpha2.py`** - Basic conversation examples (Alpha2)
  - Simple Alpha2 conversation flow

- **Configuration files:**
  - `.env.example` - Environment variables template
  - `config/` directory - Provider-specific component configurations



## Troubleshooting

### Common Issues

1. **No LLM providers configured**
   - Ensure API keys are set in environment variables or `.env` file
   - Check that component configurations are correctly formatted

2. **Tool calls not working**
   - Verify tool schema is properly formatted (use examples as reference)
   - Check that `tool_choice` is set to `'auto'` or specific tool name
   - Ensure LLM provider supports function calling

3. **Multi-turn context issues**
   - Use `convert_llm_response_to_conversation_message()` helper function
   - Maintain conversation history across turns
   - Include all previous messages in subsequent requests

4. **Parameter conversion errors**
   - Alpha2 automatically converts raw Python values to GrpcAny
   - No need to manually create GrpcAny objects for parameters
   - Supported types: int, float, bool, str, dict, list

5. **Streaming not available**
   - Response streaming is not yet supported in Alpha2
   - Set `stream: False` in parameters (this is the default)
   - All responses are returned as complete, non-streaming messages


## Features Overview

| Feature | Alpha1 | Alpha2 |
|---------|--------|--------|
| Basic Conversations | ✅ | ✅ |
| Tool Calling | ❌ | ✅ |
| Multi-turn Context | ❌ | ✅ |
| Advanced Message Types | ❌ | ✅ |
| Parameter Auto-conversion | ❌ | ✅ |
| Function-to-Schema | ❌ | ✅ |
| Async Support | ✅ | ✅ Enhanced |
| Real LLM Providers | ✅ | ✅ |

**Recommendation:** Use Alpha2 for new projects and consider migrating existing Alpha1 code to benefit from enhanced features and improved developer experience.