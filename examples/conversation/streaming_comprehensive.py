#!/usr/bin/env python3

"""
Comprehensive example demonstrating the Dapr streaming conversation API.

This example demonstrates all features of the streaming conversation API including:
- Basic streaming conversation
- Usage tracking (token consumption)
- PII scrubbing
- Temperature control
- Error handling

Prerequisites:
- Dapr sidecar running with conversation components
- Use tools/run_dapr_dev.py to start a development sidecar with echo component
"""

from dapr.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput


def basic_streaming_test(d):
    """Test basic streaming conversation."""
    print('\n📡 Testing basic streaming conversation...')
    inputs = [ConversationInput(content='Hello from Python SDK streaming test!', role='user')]

    chunks_received = []
    final_usage = None
    final_context_id = None

    for response in d.converse_stream_alpha1(
        name='echo', inputs=inputs, context_id='sync-test-session-123'
    ):
        if response.chunk:
            # Extract text from chunk parts or fallback to deprecated content
            if response.chunk.parts:
                for part in response.chunk.parts:
                    if part.text:
                        print(f'📦 Chunk: "{part.text.text}"')
                        chunks_received.append(part.text.text)
            elif response.chunk.content:
                print(f'📦 Chunk: "{response.chunk.content}"')
                chunks_received.append(response.chunk.content)
        elif response.complete:
            # Handle completion with final context and usage
            if response.complete.context_id:
                final_context_id = response.complete.context_id
                print(f'🆔 Context ID: {final_context_id}')
            if response.complete.usage:
                prompt_tokens = response.complete.usage.prompt_tokens
                completion_tokens = response.complete.usage.completion_tokens
                total_tokens = response.complete.usage.total_tokens
                usage_parts = [
                    f'📊 Usage: {prompt_tokens} prompt',
                    f'{completion_tokens} completion',
                    f'{total_tokens} total tokens',
                ]
                print(' + '.join(usage_parts[:2]) + ' = ' + usage_parts[2])
                final_usage = response.complete.usage

            # NEW: Handle accumulated outputs/tool calls in complete message
            if response.complete.outputs:
                print(f'🔧 Accumulated outputs: {len(response.complete.outputs)} items')
                for i, output in enumerate(response.complete.outputs):
                    if output.get_tool_calls():
                        tool_calls = output.get_tool_calls()
                        print(f'   Output {i+1}: {len(tool_calls)} tool call(s)')
                        for tool_call in tool_calls:
                            print(f'     - {tool_call.name}({tool_call.arguments})')
                    elif output.get_text():
                        print(f'   Output {i+1}: Text - "{output.get_text()}"')

    print(f'\n✅ Success! Received {len(chunks_received)} chunks')
    print(f'📝 Full response: {"".join(chunks_received)}')
    if final_usage:
        print(f'💰 Total usage: {final_usage.total_tokens} tokens')
    else:
        no_usage_msg = 'ℹ️  No usage information available'
        echo_note = " (echo component doesn't provide token counts)"
        print(no_usage_msg + echo_note)


def pii_scrubbing_test(d):
    """Test PII scrubbing functionality."""
    print('\n🔒 Testing PII scrubbing...')
    pii_inputs = [
        ConversationInput(content='My phone number is +1234567890', role='user', scrub_pii=True)
    ]

    scrubbed_chunks = []
    for response in d.converse_stream_alpha1(name='echo', inputs=pii_inputs, scrub_pii=True):
        if response.chunk:
            if response.chunk.parts:
                for part in response.chunk.parts:
                    if part.text:
                        print(f'📦 Scrubbed chunk: "{part.text.text}"')
                        scrubbed_chunks.append(part.text.text)
            elif response.chunk.content:
                print(f'📦 Scrubbed chunk: "{response.chunk.content}"')
                scrubbed_chunks.append(response.chunk.content)

    scrubbed_response = ''.join(scrubbed_chunks)
    print(f'📝 Scrubbed response: {scrubbed_response}')

    if '<PHONE_NUMBER>' in scrubbed_response:
        print('✅ PII scrubbing working correctly!')
    else:
        print('⚠️  PII scrubbing may not be working as expected')


def temperature_test(d):
    """Test temperature parameter."""
    print('\n🌡️ Testing with temperature parameter...')
    temp_inputs = [ConversationInput(content='Test with temperature setting', role='user')]

    temp_chunks = []
    for response in d.converse_stream_alpha1(name='echo', inputs=temp_inputs, temperature=0.7):
        if response.chunk:
            if response.chunk.parts:
                for part in response.chunk.parts:
                    if part.text:
                        temp_chunks.append(part.text.text)
            elif response.chunk.content:
                temp_chunks.append(response.chunk.content)

    print(f'📝 Temperature test response: {"".join(temp_chunks)}')


def main():
    print('🚀 Demonstrating Dapr streaming conversation API features...')

    try:
        with DaprClient() as d:
            print('✓ Connected to Dapr sidecar')
            basic_streaming_test(d)
            pii_scrubbing_test(d)
            temperature_test(d)

    except Exception as e:
        print(f'❌ Error: {e}')
        print('\n💡 Make sure to start the Dapr sidecar with:')
        print('   python tools/run_dapr_dev.py')


if __name__ == '__main__':
    main()
