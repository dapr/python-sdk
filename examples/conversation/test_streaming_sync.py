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

import time
from dapr.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput

def main():
    print('🚀 Demonstrating Dapr streaming conversation API features...')
    
    try:
        with DaprClient() as d:
            print('✓ Connected to Dapr sidecar')
            
            # Test basic streaming conversation
            print('\n📡 Testing basic streaming conversation...')
            inputs = [
                ConversationInput(content="Hello from Python SDK streaming test!", role='user')
            ]
            
            chunks_received = []
            final_usage = None
            for chunk in d.converse_stream_alpha1(
                name='echo',
                inputs=inputs,
                context_id='sync-test-session-123'
            ):
                if chunk.result and chunk.result.result:
                    print(f'📦 Chunk: "{chunk.result.result}"')
                    chunks_received.append(chunk.result.result)
                if chunk.context_id:
                    print(f'🆔 Context ID: {chunk.context_id}')
                if chunk.usage:
                    print(f'📊 Usage: {chunk.usage.prompt_tokens} prompt + {chunk.usage.completion_tokens} completion = {chunk.usage.total_tokens} total tokens')
                    final_usage = chunk.usage
            
            print(f'\n✅ Success! Received {len(chunks_received)} chunks')
            print(f'📝 Full response: {"".join(chunks_received)}')
            if final_usage:
                print(f'💰 Total usage: {final_usage.total_tokens} tokens')
            else:
                print('ℹ️  No usage information available (echo component doesn\'t provide token counts)')
            
            # Test with PII scrubbing
            print('\n🔒 Testing PII scrubbing...')
            pii_inputs = [
                ConversationInput(content="My phone number is +1234567890", role='user', scrub_pii=True)
            ]
            
            scrubbed_chunks = []
            for chunk in d.converse_stream_alpha1(
                name='echo',
                inputs=pii_inputs,
                scrub_pii=True
            ):
                if chunk.result and chunk.result.result:
                    print(f'📦 Scrubbed chunk: "{chunk.result.result}"')
                    scrubbed_chunks.append(chunk.result.result)
            
            scrubbed_response = "".join(scrubbed_chunks)
            print(f'📝 Scrubbed response: {scrubbed_response}')
            
            if "<PHONE_NUMBER>" in scrubbed_response:
                print('✅ PII scrubbing working correctly!')
            else:
                print('⚠️  PII scrubbing may not be working as expected')
                
            # Test with temperature parameter
            print('\n🌡️ Testing with temperature parameter...')
            temp_inputs = [
                ConversationInput(content="Test with temperature setting", role='user')
            ]
            
            temp_chunks = []
            for chunk in d.converse_stream_alpha1(
                name='echo',
                inputs=temp_inputs,
                temperature=0.7
            ):
                if chunk.result and chunk.result.result:
                    temp_chunks.append(chunk.result.result)
            
            print(f'📝 Temperature test response: {"".join(temp_chunks)}')

    except Exception as e:
        print(f'❌ Error: {e}')
        print('\n💡 Make sure to start the Dapr sidecar with:')
        print('   python tools/run_dapr_dev.py')

if __name__ == '__main__':
    main() 