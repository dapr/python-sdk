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

4. **Run the comprehensive example:**
   ```bash
   python examples/conversation/real_llm_providers_example.py
   ```

## Alpha2 API Features

The Alpha2 API introduces sophisticated features:

- **Advanced Message Types**: user, system, assistant, tool messages
- **Automatic Parameter Conversion**: Raw Python values → GrpcAny
- **Enhanced Tool Calling**: Multi-turn tool workflows
- **Function-to-Schema**: Ultimate DevEx for tool creation
- **Multi-turn Conversations**: Context accumulation across turns
- **Async Support**: Full async/await implementation

## New Tool Creation Helpers (Alpha2) - Excellent DevEx!

The Alpha2 API introduces powerful new helper functions that dramatically simplify tool creation and parameter handling.

### Before (Manual GrpcAny Creation) ❌
```python
from google.protobuf.any_pb2 import Any as GrpcAny
import json

# Manual, error-prone approach
location_param = GrpcAny()
location_param.value = json.dumps({
    "type": "string", 
    "description": "City name"
}).encode()

unit_param = GrpcAny()
unit_param.value = json.dumps({
    "type": "string",
    "enum": ["celsius", "fahrenheit"] 
}).encode()

weather_tool = ConversationTools(
    function=ConversationToolsFunction(
        name="get_weather",
        description="Get weather",
        parameters={
            "location": location_param,  # ✅ This part was correct
            "unit": unit_param,         # ✅ This part was correct  
            "required": ["location"]    # ❌ This causes CopyFrom errors!
        }
    )
)
```

### After (Helper Functions) ✅
```python
from dapr.clients.grpc._helpers import create_tool

# Clean, simple, intuitive approach  
weather_tool = create_tool(
    name="get_weather",
    description="Get current weather",
    parameters={
        "location": {
            "type": "string", 
            "description": "City name"
        },
        "unit": {
            "type": "string",
            "enum": ["celsius", "fahrenheit"]
        }
    },
    required=["location"]
)
```

## Understanding the Protobuf Structure

The Dapr Conversation API uses a specific protobuf structure for tool parameters that follows the OpenAI function calling standard:

```protobuf
// ConversationToolsFunction.parameters is a map<string, google.protobuf.Any>
// The parameters map directly represents the JSON schema structure
parameters: {
  "type": GrpcAny(StringValue("object")),
  "properties": GrpcAny(Struct with parameter definitions),
  "required": GrpcAny(ListValue(["location"]))
}
```

**Key insights:**
- ✅ The **parameters map IS the JSON schema** - direct field mapping
- ✅ Uses **proper protobuf types** for each schema field:
  - `"type"`: `StringValue` for the schema type
  - `"properties"`: `Struct` for parameter definitions  
  - `"required"`: `ListValue` for required field names
- ✅ **No wrapper keys** - each JSON schema field becomes a map entry
- ✅ This matches the **OpenAI function calling standard** exactly

**Example JSON Schema:**
```json
{
  "type": "object",
  "properties": {
    "location": {"type": "string", "description": "City name"},
    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
  },
  "required": ["location"]
}
```

**Becomes protobuf map:**
```python
parameters = {
    "type": GrpcAny(StringValue("object")),
    "properties": GrpcAny(Struct({
        "location": {"type": "string", "description": "City name"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
    })),
    "required": GrpcAny(ListValue(["location"]))
}
```

**Resolved Issues:**
- ❌ **Old Issue**: `'type.googleapis.com/google.protobuf.StringValue' is not of type 'object'`
- ✅ **New Solution**: Direct schema field mapping with proper protobuf types

### Automatic Parameter Conversion

Parameters are now automatically converted from raw Python types:

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

The most advanced approach: define typed Python functions and automatically generate tool schemas:

```python
from typing import Optional, List
from enum import Enum
from dapr.clients.grpc._schema_helpers import function_to_json_schema
from dapr.clients.grpc._request import ConversationToolsFunction, ConversationTools

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

# Automatically generate schema from function
schema = function_to_json_schema(get_weather)
function = ConversationToolsFunction(
    name="get_weather",
    description="Get current weather for a location",
    parameters=schema
)
weather_tool = ConversationTools(function=function)
```

**Benefits:**
- ✅ **Type Safety**: Full Python type hint support (str, int, List, Optional, Enum, etc.)
- ✅ **Auto-Documentation**: Docstring parsing for parameter descriptions
- ✅ **Ultimate DevEx**: Define functions, get tools automatically
- ✅ **90%+ less boilerplate** compared to manual schema creation

### Multiple Tool Creation Approaches

#### 1. Simple Properties (Recommended)
```python
create_tool(
    name="get_weather",
    description="Get weather",
    parameters={
        "location": {"type": "string", "description": "City"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
    },
    required=["location"]
)
```

#### 2. Full JSON Schema
```python
create_tool(
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
```

#### 3. No Parameters
```python
create_tool(
    name="get_time",
    description="Get current time"
)
```

#### 4. Complex Schema with Arrays
```python
create_tool(
    name="search",
    description="Search the web", 
    parameters={
        "query": {"type": "string"},
        "domains": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    required=["query"]
)
```

## Advanced Message Types (Alpha2)

Alpha2 supports sophisticated message structures for complex conversations:

### User Messages
```python
from dapr.clients.grpc._request import (
    ConversationMessage,
    ConversationMessageOfUser,
    ConversationMessageContent
)

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
from dapr.clients.grpc._request import ConversationInputAlpha2

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

- ✅ **80%+ less boilerplate code**
- ✅ **No more CopyFrom() errors**
- ✅ **Automatic type conversion**
- ✅ **Multiple input formats**
- ✅ **JSON Schema validation hints**
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
from dapr.clients.grpc._response import ConversationResultMessage

def convert_llm_response_to_conversation_message(result_message: ConversationResultMessage) -> ConversationMessage:
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
  - Advanced tool calling workflows  
  - Multi-turn conversations with context accumulation
  - Function-to-schema automatic tool generation
  - Both sync and async implementations
  - Parameter conversion demonstration
  - Backward compatibility with Alpha1

- **`conversation.py`** - Basic conversation examples
  - Simple Alpha1 conversation flow
  - Basic tool calling setup

- **Configuration files:**
  - `.env.example` - Environment variables template
  - `config/` directory - Provider-specific component configurations

## Quick Start

### Basic Alpha2 Conversation with Tool Calling

```python
from dapr.clients import DaprClient
from dapr.clients.grpc._request import (
    ConversationInputAlpha2,
    ConversationMessage,
    ConversationMessageOfUser,
    ConversationMessageContent,
    ConversationToolsFunction,
    ConversationTools
)

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
            'temperature': 0.7,      # Auto-converted to GrpcAny!
            'max_tokens': 500,       # Auto-converted to GrpcAny!
            'stream': False          # Auto-converted to GrpcAny!
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

### Environment Variables

```bash
# Required for respective providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
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
from dapr.clients.grpc._request import ConversationInput

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
from dapr.clients.grpc._request import ConversationInputAlpha2, ConversationMessage

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
| Tool Calling | ✅ | ✅ Enhanced |
| Multi-turn Context | ❌ | ✅ |
| Advanced Message Types | ❌ | ✅ |
| Parameter Auto-conversion | ❌ | ✅ |
| Function-to-Schema | ❌ | ✅ |
| Async Support | ✅ | ✅ Enhanced |
| Real LLM Providers | ✅ | ✅ |

**Recommendation:** Use Alpha2 for new projects and consider migrating existing Alpha1 code to benefit from enhanced features and improved developer experience.