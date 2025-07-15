# Conversation API Examples

This directory contains examples demonstrating the Dapr Conversation API functionality in the Python SDK.

## Overview

This directory contains **10 focused examples** demonstrating the Dapr Conversation API functionality, including **tool calling (function calling)**, **streaming responses**, **parameter conversion**, and **cost tracking** with real LLM providers.

## 🎯 What You'll Learn

- **🔧 Tool Calling**: Complete function calling workflow with real LLMs
- **📡 Streaming Conversations**: Real-time response streaming from LLMs
- **🔄 Multi-Provider Support**: Work with OpenAI, Anthropic, Google, Mistral, and DeepSeek
- **⚡ Parameter Conversion**: Use simple Python values instead of complex protobuf objects
- **💰 Cost Tracking**: Monitor token consumption and costs across providers
- **🌐 Async/Sync Patterns**: Both synchronous and asynchronous implementations
- **💬 Context Management**: Maintain conversation state across exchanges
- **🧠 Conversation History**: Simplified multi-turn conversation management

## Prerequisites

### Standard Dapr Setup

1. **Dapr Installation**: 
   ```bash
   dapr init
   ```

2. **Python Dependencies**:
   ```bash
   pip install -r ../../dev-requirements.txt
   ```

3. **API Keys** (for real providers):
   ```bash
   export OPENAI_API_KEY="your-openai-key"
   export ANTHROPIC_API_KEY="your-anthropic-key"  
   export GOOGLE_API_KEY="your-google-key"
   ```

## Quick Start

### Start Dapr Sidecar

```bash
# For development/testing with echo component
python ../../tools/run_dapr_dev.py

# Or standard Dapr sidecar with your components
dapr run --app-id conversation-app \
         --dapr-http-port 3500 \
         --dapr-grpc-port 50001 \
         --resources-path ./components
```

### Run Examples

```bash
# Start with basic conversation
python conversation.py

# Try the new parameter conversion feature  
python parameter_conversion_example.py

# Test with real AI providers
python real_llm_providers_example.py
```

## 📁 Examples Overview

### 🚀 **Getting Started**

| Example | Description | Use Case |
|---------|-------------|----------|
| `conversation.py` | Basic conversation starter | First steps with Conversation API |
| `parameter_conversion_example.py` | **NEW!** Simple parameter usage | Learn the improved developer experience |

### 🤖 **Real AI Providers**

| Example | Description | Use Case |
|---------|-------------|----------|
| `real_llm_providers_example.py` | Multiple AI providers | Production usage with OpenAI, Anthropic, Google |

### 🔧 **Tool Calling**

| Example | Description | Use Case |
|---------|-------------|----------|
| `working_multi_turn_example.py` | Simple tool calling | Learn tool calling basics |
| `multi_turn_tool_calling_example.py` | Advanced multi-tool example | Complex tool calling scenarios |

### 📡 **Streaming**

| Example | Description | Use Case |
|---------|-------------|----------|
| `streaming_comprehensive.py` | Sync streaming | Real-time responses (synchronous) |
| `streaming_async_comprehensive.py` | Async streaming | Real-time responses (asynchronous) |
| `streaming_json_example.py` | JSON streaming format | OpenAI-compatible streaming |

### 💰 **Advanced Features**

| Example | Description | Use Case |
|---------|-------------|----------|
| `cost_calculation_example.py` | Cost tracking & provider comparison | Monitor usage and costs |
| `conversation_history_helper.py` | Advanced conversation management | Complex conversation state |

## 🌟 **Recommended Learning Path**

### 1. **Start Here** - Basic Concepts
```bash
python conversation.py                    # Basic conversation
python parameter_conversion_example.py   # New parameter conversion
```

### 2. **Real AI Providers**
```bash
python real_llm_providers_example.py     # Production usage
```

### 3. **Tool Calling**
```bash
python working_multi_turn_example.py     # Simple tools
python multi_turn_tool_calling_example.py # Advanced tools
```

### 4. **Streaming**
```bash
python streaming_comprehensive.py        # Sync streaming
python streaming_async_comprehensive.py  # Async streaming
```

### 5. **Advanced Features**
```bash
python cost_calculation_example.py       # Cost tracking
python conversation_history_helper.py    # Advanced management
```

## 🔧 **Key Features Demonstrated**

### ⚡ **Parameter Conversion** (NEW!)
Before our improvement:
```python
# Old way - complex protobuf wrapping
from google.protobuf.any_pb2 import Any as ProtobufAny
from google.protobuf.wrappers_pb2 import StringValue
tool_choice_any = ProtobufAny()
tool_choice_any.Pack(StringValue(value="auto"))
parameters = {"tool_choice": tool_choice_any}
```

After our improvement:
```python
# New way - simple Python values
parameters = {
    "tool_choice": "auto",        # Raw string - auto-converted
    "temperature": 0.7,           # Raw float - auto-converted  
    "max_tokens": 1000,          # Raw int - auto-converted
    "stream": False,             # Raw bool - auto-converted
}
```

### 🔧 **Tool Calling**
```python
# Define tools
weather_tool = Tool(
    type="function",
    function=ToolFunction(
        name="get_weather",
        description="Get weather information",
        parameters={...}
    )
)

# Use with ContentPart approach
inputs = [ConversationInput(
    role="user",
    parts=[
        ContentPart(text=TextContent(text="What's the weather?")),
        ContentPart(tool_definitions=ToolDefinitionsContent(tools=[weather_tool]))
    ]
)]
```

### 📡 **Streaming**
```python
# Sync streaming
for chunk in client.converse_stream_alpha1(name="openai", inputs=inputs):
    print(chunk.outputs[0].result)

# Async streaming  
async for chunk in client.converse_stream_alpha1(name="openai", inputs=inputs):
    print(chunk.outputs[0].result)
```

### 💰 **Cost Tracking**
```python
# Automatic cost calculation with provider-specific pricing
usage_info = UsageInfo.calculate_cost(
    usage,
    cost_per_million_input_tokens=0.15,   # GPT-4o-mini input
    cost_per_million_output_tokens=0.60,  # GPT-4o-mini output
    model="gpt-4o-mini",
    provider="openai"
)
```

## 🗂️ **Component Configuration**

### Echo Component (Testing)
```yaml
# components/echo.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: echo
spec:
  type: conversation.echo
  version: v1
```

### OpenAI Component
```yaml
# components/openai.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: openai
spec:
  type: conversation.openai
  version: v1
  metadata:
  - name: apiKey
    secretKeyRef:
      name: openai-secret
      key: api-key
```

### Anthropic Component
```yaml
# components/anthropic.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: anthropic
spec:
  type: conversation.anthropic
  version: v1
  metadata:
  - name: apiKey
    secretKeyRef:
      name: anthropic-secret
      key: api-key
```

## 🆘 **Troubleshooting**

### Common Issues

**Port Already in Use**
```bash
# Kill existing Dapr processes
pkill -f daprd
# Or find and kill specific process
lsof -i :50001
```

**Missing API Keys**
```bash
# Set environment variables
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
export GOOGLE_API_KEY="your-key-here"
```

**Component Not Found**
```bash
# Ensure components are in the correct path
ls -la components/
# Or specify path explicitly
dapr run --resources-path ./components ...
```

## 📚 **Additional Resources**

- [Dapr Conversation API Documentation](https://docs.dapr.io/developing-applications/building-blocks/conversation/)
- [Dapr Python SDK Documentation](https://docs.dapr.io/developing-applications/sdks/python/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Anthropic Claude API Documentation](https://docs.anthropic.com/claude/reference/)

## 🎉 **What's New**

### Recent Improvements

- ✅ **Parameter Conversion**: No more protobuf complexity - use simple Python values!
- ✅ **Streamlined Examples**: Reduced from 48+ files to 10 focused examples
- ✅ **Fixed Cost Calculations**: Accurate pricing for all providers
- ✅ **Current API Usage**: All examples use modern ContentPart approach
- ✅ **Comprehensive Testing**: All examples tested and working

### Breaking Changes

- ❌ **Removed `tools=` parameter**: Use ContentPart with ToolDefinitionsContent instead
- ❌ **Removed obsolete examples**: Consolidated into focused, working examples
- ❌ **Fixed pricing bugs**: Corrected 1000x calculation errors in cost examples

---

**💡 Tip**: Start with `conversation.py` and `parameter_conversion_example.py` to understand the basics, then explore the other examples based on your specific needs!