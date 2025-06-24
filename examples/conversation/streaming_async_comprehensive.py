#!/usr/bin/env python3

"""
Example demonstrating asynchronous streaming conversation API.

This example shows how to use the Dapr async conversation streaming API with the echo component
for testing purposes. In production, you would replace 'echo' with an actual LLM component
like 'openai', 'anthropic', etc.

Prerequisites:
- Dapr sidecar running with conversation components
- Use tools/run_dapr_dev.py to start a development sidecar with echo component
"""

import asyncio

from dapr.aio.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput


async def basic_streaming_test(d):
    """Test basic async streaming conversation."""
    print('\n📡 Testing async streaming conversation...')
    inputs = [ConversationInput(content='Hello from async Python SDK streaming test!', role='user')]

    chunks_received = []
    final_usage = None
    async for chunk in d.converse_stream_alpha1(
        name='echo', inputs=inputs, context_id='async-test-session-456'
    ):
        if chunk.result and chunk.result.result:
            print(f'📦 Async chunk: "{chunk.result.result}"')
            chunks_received.append(chunk.result.result)
        if chunk.context_id:
            print(f'🆔 Async context ID: {chunk.context_id}')
        if chunk.usage:
            prompt_tokens = chunk.usage.prompt_tokens
            completion_tokens = chunk.usage.completion_tokens
            total_tokens = chunk.usage.total_tokens
            usage_parts = [
                f'📊 Async usage: {prompt_tokens} prompt',
                f'{completion_tokens} completion',
                f'{total_tokens} total tokens',
            ]
            print(' + '.join(usage_parts[:2]) + ' = ' + usage_parts[2])
            final_usage = chunk.usage

    print(f'\n✅ Async success! Received {len(chunks_received)} chunks')
    print(f'📝 Full async response: {"".join(chunks_received)}')
    if final_usage:
        print(f'💰 Total async usage: {final_usage.total_tokens} tokens')
    else:
        no_usage_msg = 'ℹ️  No usage information available'
        echo_note = " (echo component doesn't provide token counts)"
        print(no_usage_msg + echo_note)


async def concurrent_conversations_test(d):
    """Test multiple concurrent conversations."""
    print('\n🔄 Testing concurrent conversations...')

    async def run_conversation(message, session_id):
        inputs = [ConversationInput(content=message, role='user')]
        chunks = []
        async for chunk in d.converse_stream_alpha1(
            name='echo', inputs=inputs, context_id=session_id
        ):
            if chunk.result and chunk.result.result:
                chunks.append(chunk.result.result)
        return f"Session {session_id}: {''.join(chunks)}"

    # Run 3 conversations concurrently
    tasks = [
        run_conversation('First conversation', 'session-1'),
        run_conversation('Second conversation', 'session-2'),
        run_conversation('Third conversation', 'session-3'),
    ]

    results = await asyncio.gather(*tasks)
    for result in results:
        print(f'🎯 {result}')


async def main():
    print('🧪 Testing asynchronous streaming conversation with echo component...')

    try:
        async with DaprClient() as d:
            print('✓ Connected to Dapr sidecar (async)')
            await basic_streaming_test(d)
            await concurrent_conversations_test(d)

    except Exception as e:
        print(f'❌ Async error: {e}')
        print('\n💡 Make sure to start the Dapr sidecar with:')
        print('   python tools/run_dapr_dev.py')


if __name__ == '__main__':
    asyncio.run(main())
