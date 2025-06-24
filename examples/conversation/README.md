# Conversation Streaming Examples

This directory contains examples demonstrating the Dapr conversation streaming API functionality in the Python SDK.

## Overview

The conversation streaming API allows you to interact with AI/LLM models through Dapr components in a streaming fashion, receiving responses as they are generated rather than waiting for the complete response.

## Features Demonstrated

- **Synchronous streaming**: Use regular Python iterators to receive streaming responses
- **Asynchronous streaming**: Use `async for` to receive streaming responses in async code
- **Context management**: Maintain conversation context across multiple exchanges
- **PII scrubbing**: Automatically scrub personally identifiable information from responses
- **Temperature control**: Control response randomness/creativity
- **Usage tracking**: Monitor token consumption (prompt, completion, total tokens)
- **Concurrent conversations**: Handle multiple conversations simultaneously (async)

## Prerequisites

1. **Local Dapr Repository**: Clone the Dapr repository alongside this Python SDK:
   ```bash
   git clone https://github.com/dapr/dapr.git ../dapr
   ```

2. **Python Dependencies**: Install the development dependencies:
   ```bash
   pip install -r dev-requirements.txt
   ```

## Quick Start

### 1. Start the Development Sidecar

Use the provided development helper to build and run a Dapr sidecar with conversation components:

```bash
# Build and run (first time)
python tools/run_dapr_dev.py --build

# Just run (if already built)
python tools/run_dapr_dev.py
```

This will:
- Build the latest daprd binary from your local Dapr repository
- Create temporary conversation components (echo component for testing)
- Start the sidecar on default ports (HTTP: 3500, gRPC: 50001)

### 2. Run the Examples

In a separate terminal, run the streaming examples:

```bash
# Comprehensive streaming example (synchronous)
python examples/conversation/streaming_comprehensive.py

# Comprehensive async streaming example
python examples/conversation/streaming_async_comprehensive.py
```

## Examples

### Comprehensive Streaming (`streaming_comprehensive.py`)

Demonstrates:
- Basic streaming conversation with echo component
- PII scrubbing functionality
- Temperature parameter usage
- Context ID management
- Usage tracking (token consumption)
- Error handling

### Comprehensive Async Streaming (`streaming_async_comprehensive.py`)

Demonstrates:
- Async streaming conversation
- Concurrent multiple conversations
- Proper async context management
- Usage tracking
- Error handling

## Development Helper (`tools/run_dapr_dev.py`)

The development helper script provides convenient options for testing:

```bash
# Build and run with default settings
python tools/run_dapr_dev.py --build

# Run with custom ports and debug logging
python tools/run_dapr_dev.py --port 3501 --grpc-port 50002 --log-level debug

# Use existing component configuration
python tools/run_dapr_dev.py --components ./my-components

# Just build without running
python tools/run_dapr_dev.py --build --help
```

## Component Configuration

The examples use an "echo" conversation component that simply echoes back the input, useful for testing. The component configuration is automatically created:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: echo
spec:
  type: conversation.echo
  version: v1
  metadata:
  - name: key
    value: testkey
```

For production use, replace this with actual LLM components like:
- `conversation.openai`
- `conversation.anthropic` 
- `conversation.azure-openai`
- etc.

## API Reference

### Synchronous Client

```python
from dapr.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput

with DaprClient() as client:
    inputs = [ConversationInput(content="Hello!", role='user')]
    
    for chunk in client.converse_stream_alpha1(
        name='echo',
        inputs=inputs,
        context_id='session-123',
        temperature=0.7,
        scrub_pii=True
         ):
         if chunk.result and chunk.result.result:
             print(chunk.result.result)
         if chunk.context_id:
             print(f"Context: {chunk.context_id}")
         if chunk.usage:
             print(f"Usage: {chunk.usage.total_tokens} tokens")
```

### Asynchronous Client

```python
from dapr.aio.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput

async with DaprClient() as client:
    inputs = [ConversationInput(content="Hello!", role='user')]
    
    async for chunk in client.converse_stream_alpha1(
        name='echo',
        inputs=inputs,
        context_id='session-123'
    ):
        if chunk.result and chunk.result.result:
            print(chunk.result.result)
```

## Troubleshooting

### "Connection refused" errors
- Make sure the Dapr sidecar is running: `python tools/run_dapr_dev.py`
- Check that ports 3500 and 50001 are not in use by other processes

### "Component not found" errors  
- Verify the conversation components are loaded (check sidecar logs)
- Make sure you're using the correct component name ('echo' in examples)

### Build errors
- Ensure Go is installed and the Dapr repository is properly cloned
- Try running `make build` manually in the `../dapr` directory

### Import errors
- Install development dependencies: `pip install -r dev-requirements.txt`
- Make sure you're in the correct Python environment

## Contributing

When modifying the conversation streaming implementation:

1. Update the examples to demonstrate new features
2. Test both sync and async implementations
3. Verify PII scrubbing and other parameters work correctly
4. Update this README if adding new functionality

## Related Files

- `dapr/clients/grpc/client.py` - Synchronous client implementation
- `dapr/aio/clients/grpc/client.py` - Asynchronous client implementation  
- `dapr/clients/grpc/_response.py` - Response type definitions
- `tools/run_dapr_dev.py` - Development helper script