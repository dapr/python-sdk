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

6. **Run the comprehensive example with real LLM providers (This requires API Keys)**

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

### Simple JSON Schema Approach
```python
# Clean, simple, intuitive approach using standard JSON schema
function = ConversationToolsFunction(
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
weather_tool = ConversationTools(function=function)
```

## Understanding the Protobuf Structure

The Dapr Conversation API uses a protobuf Struct to represent JSON schema for tool parameters, which directly maps to JSON:

```python
# ConversationToolsFunction.parameters is a protobuf Struct (Dict[str, Any])
# The parameters directly represent the JSON schema structure
parameters = {
    "type": "object",
    "properties": {
        "location": {"type": "string", "description": "City name"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
    },
    "required": ["location"]
}
```

**Key insights:**
- ✅ **Direct JSON representation** - parameters is a standard Python dict that gets converted to protobuf Struct
- ✅ **Clean developer experience** - write standard JSON schema as Python dict
- ✅ **OpenAI function calling standard** - follows OpenAI's JSON schema format

**Benefits of Struct-based approach:**

- Direct JSON schema representation
- Automatic type conversion
- Better error messages and debugging

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


### Function-to-Schema Approach (Ultimate DevEx!)

We provide a helper function to automatically generate the tool schema from a Python function.

```python
from typing import Optional, List
from enum import Enum
from dapr.clients.grpc._conversation import ConversationToolsFunction, ConversationTools


class Units(Enum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


def get_weather(location: str, unit: Units = Units.FAHRENHEIT) -> str:
    '''Get current weather for a location.

    Args:
        location: The city and state or country
        unit: Temperature unit preference
    '''
    return f"Weather in {location}"


# Use the from_function class method for automatic schema generation
function = ConversationToolsFunction.from_function(get_weather)
weather_tool = ConversationTools(function=function)
```

**Benefits:**
- ✅ **Type Safety**: Full Python type hint support (str, int, List, Optional, Enum, etc.)
- ✅ **Auto-Documentation**: Docstring parsing for parameter descriptions
- ✅ **Ultimate DevEx**: Define functions, get tools automatically
- ✅ **90%+ less boilerplate** compared to manual schema creation

### Multiple Tool Creation Approaches

#### 1. Simple JSON Schema (Recommended)
```python
function = ConversationToolsFunction(
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
weather_tool = ConversationTools(function=function)
```

#### 2. Complete JSON Schema
```python
function = ConversationToolsFunction(
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
calc_tool = ConversationTools(function=function)
```

#### 3. No Parameters
```python
function = ConversationToolsFunction(
    name="get_time",
    description="Get current time",
    parameters={"type": "object", "properties": {}, "required": []}
)
time_tool = ConversationTools(function=function)
```

#### 4. Complex Schema with Arrays
```python
function = ConversationToolsFunction(
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
search_tool = ConversationTools(function=function)
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

from dapr.clients.grpc._conversation import ConversationInputAlpha2

# Build conversation history
conversation_history = []

# Turn 1: User asks question
user_message = create_user_message("What's the weather in San Francisco?")
conversation_history.append(user_message)

# LLM responds (potentially with tool calls)
response1 = client.converse_alpha2(
    name="openai",
    inputs=[ConversationInputAlpha2(messages=conversation_history)],
    tools=[weather_tool]
)

# Add LLM response to history
assistant_message = convert_llm_response_to_conversation_message(response1.outputs[0].choices[0].message)
conversation_history.append(assistant_message)

# Turn 2: Follow-up question with full context
user_message2 = create_user_message("Should I bring an umbrella?")
conversation_history.append(user_message2)

response2 = client.converse_alpha2(
    name="openai",
    inputs=[ConversationInputAlpha2(messages=conversation_history)],
    tools=[weather_tool]
)
```

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
  - Async conversation and tool calling support
  - Backward compatibility with Alpha1

- **`conversation_alpha1.py`** - Basic conversation examples (Alpha1)
  - Simple Alpha1 conversation flow
- **`conversation_alpha2.py`** - Basic conversation examples (Alpha2)
  - Simple Alpha2 conversation flow

- **Configuration files:**
  - `.env.example` - Environment variables template
  - `config/` directory - Provider-specific component configurations

## Quick Start

### Basic Alpha2 Conversation with Tool Calling

```python
from dapr.clients import DaprClient
from dapr.clients.grpc._request import (
    ConversationTools
)
from dapr.clients.grpc._conversation import ConversationMessageContent, ConversationMessageOfUser, ConversationMessage,

ConversationToolsFunction
ConversationInputAlpha2

# Create a tool using the simple approach
function = ConversationToolsFunction(
    name="get_weather",
    description="Get current weather for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state or country"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit"
            }
        },
        "required": ["location"]
    }
)
weather_tool = ConversationTools(function=function)

# Create a user message
user_message = ConversationMessage(
    of_user=ConversationMessageOfUser(
        content=[ConversationMessageContent(text="What's the weather in Paris?")]
    )
)

# Create input and make the request
input_alpha2 = ConversationInputAlpha2(messages=[user_message])

with DaprClient() as client:
    response = client.converse_alpha2(
        name="openai",  # or "anthropic", "mistral", etc.
        inputs=[input_alpha2],
        parameters={
            'temperature': 0.7,  # Auto-converted to GrpcAny!
            'max_tokens': 500,  # Auto-converted to GrpcAny!
            'stream': False  # Streaming not supported in Alpha2
        },
        tools=[weather_tool],
        tool_choice='auto'
    )

    # Process the response
    if response.outputs and response.outputs[0].choices:
        choice = response.outputs[0].choices[0]
        if choice.finish_reason == 'tool_calls' and choice.message.tool_calls:
            print(f"LLM wants to call: {choice.message.tool_calls[0].function.name}")
            print(f"With arguments: {choice.message.tool_calls[0].function.arguments}")
        else:
            print(f"LLM response: {choice.message.content}")
```

### Real Provider Setup

1. Set up environment:
   ```bash
   export OPENAI_API_KEY="your_key_here"
   ```

2. Create component configuration (`components/openai.yaml`):
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

3. Start Dapr sidecar:
   ```bash
   dapr run --app-id test-app --dapr-grpc-port 50001 --resources-path ./components/
   ```

4. Run your conversation code!

For a complete working example with multiple providers, see `real_llm_providers_example.py`.

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

### Environment Variables

```bash
# Required for respective providers
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
MISTRAL_API_KEY=...
DEEPSEEK_API_KEY=...
GOOGLE_API_KEY=...

# Optional: Use local development build
USE_LOCAL_DEV=true
BUILD_LOCAL_DAPR=true
```

## Migration from Alpha1 to Alpha2

Alpha2 provides significant improvements while maintaining backward compatibility:

### Alpha1 (Legacy)

```python

from dapr.clients.grpc._conversation import ConversationInput

inputs = [ConversationInput(
    content="Hello!",
    role="user"
)]

response = client.converse_alpha1(
    name="provider",
    inputs=inputs,
    parameters={'temperature': 0.7}
)
```

### Alpha2 (Recommended)

```python

from dapr.clients.grpc._conversation import ConversationMessage, ConversationInputAlpha2

user_message = ConversationMessage(
    of_user=ConversationMessageOfUser(
        content=[ConversationMessageContent(text="Hello!")]
    )
)

response = client.converse_alpha2(
    name="provider",
    inputs=[ConversationInputAlpha2(messages=[user_message])],
    parameters={'temperature': 0.7}  # Auto-converted!
)
```

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