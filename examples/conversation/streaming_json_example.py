#!/usr/bin/env python3

"""
Example demonstrating the new converse_stream_json API.

This example shows how to use the new JSON-formatted streaming conversation API
that provides responses compatible with common LLM response formats, making it
easier to integrate with existing tools and frameworks.

Prerequisites:
- Dapr sidecar running with conversation components
- Use tools/run_dapr_dev.py to start a development sidecar with echo component
"""

import asyncio

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput


def sync_json_streaming_example():
    """Demonstrate synchronous JSON streaming conversation."""
    print('🚀 Testing synchronous JSON streaming conversation...')

    with DaprClient() as d:
        print('✓ Connected to Dapr sidecar')

        inputs = [ConversationInput(content='Hello from JSON streaming test!', role='user')]

        print('\n📡 Streaming with JSON format...')
        for chunk in d.converse_stream_json(
            name='echo', inputs=inputs, context_id='json-test-session'
        ):
            print(f'📦 JSON chunk: {chunk}')

            # Extract content from the JSON structure
            choices = chunk.get('choices', [])
            if choices and choices[0].get('delta', {}).get('content'):
                content = choices[0]['delta']['content']
                print(f'   Content: "{content}"')

            # Check for context ID
            if chunk.get('context_id'):
                print(f'   Context ID: {chunk["context_id"]}')

            # Check for usage information
            if chunk.get('usage'):
                usage = chunk['usage']
                prompt_tokens = usage['prompt_tokens']
                completion_tokens = usage['completion_tokens']
                total_tokens = usage['total_tokens']
                print(f'   Usage: {prompt_tokens} + {completion_tokens} = {total_tokens} tokens')


async def async_json_streaming_example():
    """Demonstrate asynchronous JSON streaming conversation."""
    print('\n🧪 Testing asynchronous JSON streaming conversation...')

    async with AsyncDaprClient() as d:
        print('✓ Connected to Dapr sidecar (async)')

        inputs = [ConversationInput(content='Hello from async JSON streaming test!', role='user')]

        print('\n📡 Async streaming with JSON format...')
        async for chunk in d.converse_stream_json(
            name='echo', inputs=inputs, context_id='async-json-test-session'
        ):
            print(f'📦 Async JSON chunk: {chunk}')

            # Extract content from the JSON structure
            choices = chunk.get('choices', [])
            if choices and choices[0].get('delta', {}).get('content'):
                content = choices[0]['delta']['content']
                print(f'   Async Content: "{content}"')

            # Check for context ID
            if chunk.get('context_id'):
                print(f'   Async Context ID: {chunk["context_id"]}')

            # Check for usage information
            if chunk.get('usage'):
                usage = chunk['usage']
                prompt_tokens = usage['prompt_tokens']
                completion_tokens = usage['completion_tokens']
                total_tokens = usage['total_tokens']
                usage_parts = [
                    f'   Async Usage: {prompt_tokens}',
                    f'{completion_tokens}',
                    f'{total_tokens} tokens',
                ]
                print(' + '.join(usage_parts[:2]) + ' = ' + usage_parts[2])


def main():
    """Run both sync and async examples."""
    try:
        # Run synchronous example
        sync_json_streaming_example()

        # Run asynchronous example
        asyncio.run(async_json_streaming_example())

        print('\n✅ JSON streaming examples completed successfully!')
        json_compat_msg = '\n💡 The JSON format is compatible with common LLM APIs like OpenAI.'
        integration_msg = '   This makes it easier to integrate with existing tools and frameworks.'
        print(json_compat_msg)
        print(integration_msg)

    except Exception as e:
        print(f'❌ Error: {e}')
        print('\n💡 Make sure to start the Dapr sidecar with:')
        print('   python tools/run_dapr_dev.py')


if __name__ == '__main__':
    main()
