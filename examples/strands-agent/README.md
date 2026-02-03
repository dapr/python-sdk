# Dapr For Agents - Strands Agent with Persistent Session Storage

Supporting Dapr-backed session persistence for Strands Agent SDK with distributed state storage.

## Overview

This example demonstrates how to use a **real Strands Agent** from the Strands Agent SDK together with `DaprSessionManager` for distributed session persistence. The example shows:

- Creating a Strands Agent with the official Strands SDK
- Using DaprSessionManager for distributed session storage across restarts
- Tool integration (weather checking example)
- Conversation history persistence and restoration
- Seamless LLM integration through Strands model providers

**Note:** This uses the actual [Strands Agent SDK](https://strandsagents.com/), not just session types.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)
- OpenAI API key (or configure a different model provider)

## Install Dependencies

```sh
pip3 install -r requirements.txt
```

Set your API key:
```sh
export OPENAI_API_KEY=your-key-here
```

## Run the Example

Run the following command in a terminal/command prompt:

```sh
dapr run --app-id strands-agent --resources-path ./components -- python3 agent.py
```

### What to Expect

The example will:

1. Create a Strands Agent with:
   - GPT-4o model via OpenAIModel provider
   - A `get_weather` tool function
   - System prompt and agent metadata
   - DaprSessionManager for session persistence
2. Process user queries:
   - "What's the weather in San Francisco?" → Agent uses get_weather tool
   - "How about New York?" → Agent continues conversation with context
3. Persist all conversation state to Dapr state store
4. On subsequent runs, automatically restore full conversation history

Run the example again to see the conversation resume from where it left off!

### Example Output

**First run:**
```
📂 Using session: assistant-session-1
✅ Created Strands Agent: weather-assistant
   Model: OpenAIModel(model='gpt-4o')
   Tools: ['get_weather']
   Session Manager: DaprSessionManager

🆕 Starting fresh conversation

👤 USER: What's the weather in San Francisco?
🤖 ASSISTANT: The weather in San Francisco is sunny and 72°F

👤 USER: How about New York?
🤖 ASSISTANT: Let me check that for you. The weather in New York is sunny and 72°F

✅ Conversation complete!
🔄 Run again to resume the conversation with full history from Dapr state store.
```

**Second run (conversation resumes):**
```
📂 Using session: assistant-session-1
✅ Created Strands Agent: weather-assistant
   Model: OpenAIModel(model='gpt-4o')
   Tools: ['get_weather']
   Session Manager: DaprSessionManager

💬 Resuming conversation with 4 previous messages
────────────────────────────────────────────────────────────
👤 USER: What's the weather in San Francisco?
🤖 ASSISTANT: The weather in San Francisco is sunny and 72°F
👤 USER: How about New York?
🤖 ASSISTANT: Let me check that for you. The weather in New York is sunny and 72°F
────────────────────────────────────────────────────────────

👤 USER: What's the weather in San Francisco?
🤖 ASSISTANT: I just checked that - it's still sunny and 72°F in San Francisco!
```

## Key Features

### Real Strands Agent
- Uses the official Strands Agent SDK from strandsagents.com
- Full agent capabilities: tools, system prompts, state management
- Multiple LLM provider support (Anthropic, OpenAI, Bedrock, etc.)

### Distributed Session Persistence
- DaprSessionManager stores all conversation state in Dapr state stores
- Supports any Dapr state store: Redis, PostgreSQL, MongoDB, Cosmos DB, etc.
- Automatic conversation restoration across application restarts
- Full message history maintained

### Tool Integration
- Define Python functions as tools
- Agent automatically calls tools when needed
- Tool results integrated into conversation flow

### LLM Provider Flexibility
- Easy to swap model providers (AnthropicModel, OpenAIModel, etc.)
- Configure model parameters (temperature, max tokens, etc.)
- Strands handles all LLM interactions

### State Persistence
- Automatic state synchronization with Dapr
- Support for TTL and consistency levels
- Compatible with any Dapr state store (Redis, PostgreSQL, Cosmos DB, etc.)

## Customization

You can customize the session manager with:

```python
session_manager = DaprSessionManager(
    session_id='my-session',
    state_store_name='statestore',
    dapr_client=dapr_client,
    ttl=3600,  # Optional: TTL in seconds
    consistency='strong',  # Optional: 'eventual' or 'strong'
)
```

## Configuration

### State Store

The example uses a Redis state store component. You can modify [components/statestore.yaml](./components/statestore.yaml) to use a different state store backend supported by Dapr.

### Conversation Provider

The example uses the `echo` conversation component by default (which echoes back your input). To use a real LLM:

1. Set up a conversation component (e.g., OpenAI, Anthropic) in `components/conversation.yaml`
2. Update the `conversation_provider` variable in `agent.py` to match your component name
3. Set required API keys as environment variables

Example for OpenAI:
```bash
export OPENAI_API_KEY="your-api-key"
```

See [examples/conversation](../conversation/) for more conversation component examples.

## Learn More

- [Dapr State Management](https://docs.dapr.io/developing-applications/building-blocks/state-management/)
- [Strands Framework](https://github.com/microsoft/strands)
- [Dapr Python SDK](https://github.com/dapr/python-sdk)
