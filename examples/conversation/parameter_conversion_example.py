#!/usr/bin/env python3
"""
Parameter Conversion Example for Conversation API

This example demonstrates the improved developer experience with automatic
parameter conversion. Developers can now pass raw Python values instead of
manually wrapping them in protobuf Any objects.

Before this fix, developers had to write complex protobuf wrapping code.
After this fix, the SDK handles the conversion automatically.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dapr.clients import DaprClient
from dapr.clients.grpc._request import ConversationInput


def demonstrate_old_way():
    """
    This shows how developers HAD to write code before the fix.
    (This is just for demonstration - don't actually use this approach)
    """
    print('❌ OLD WAY (Complex and Error-Prone):')
    print('=' * 50)

    # This is what developers had to do before the fix
    code_example = """
from google.protobuf.any_pb2 import Any as ProtobufAny
from google.protobuf.wrappers_pb2 import StringValue, DoubleValue, Int32Value, BoolValue

# Manual protobuf wrapping (error-prone and verbose)
tool_choice_any = ProtobufAny()
tool_choice_any.Pack(StringValue(value="auto"))

temperature_any = ProtobufAny()
temperature_any.Pack(DoubleValue(value=0.7))

max_tokens_any = ProtobufAny()
max_tokens_any.Pack(Int32Value(value=1000))

stream_any = ProtobufAny()
stream_any.Pack(BoolValue(value=False))

# Complex parameter construction
parameters = {
    "tool_choice": tool_choice_any,
    "temperature": temperature_any,
    "max_tokens": max_tokens_any,
    "stream": stream_any
}

response = client.converse_alpha1(
    name="openai",
    inputs=inputs,
    parameters=parameters  # Pre-wrapped protobuf objects
)
"""

    print(code_example)
    print('❌ Problems with the old way:')
    print('   • Requires deep protobuf knowledge')
    print('   • Verbose and error-prone')
    print('   • Cryptic error messages when wrong')
    print('   • Poor developer experience')


def demonstrate_new_way():
    """
    This shows the new, improved developer experience after the fix.
    """
    print('\n✅ NEW WAY (Simple and Intuitive):')
    print('=' * 50)

    code_example = """
# Simple, intuitive parameter passing (automatic conversion)
response = client.converse_alpha1(
    name="openai",
    inputs=inputs,
    parameters={
        "tool_choice": "auto",        # Raw string - auto-converted
        "temperature": 0.7,           # Raw float - auto-converted
        "max_tokens": 1000,          # Raw int - auto-converted
        "stream": False,             # Raw bool - auto-converted
        "top_p": 0.9,               # Raw float - auto-converted
        "frequency_penalty": 0.0,    # Raw float - auto-converted
        "presence_penalty": 0.0,     # Raw float - auto-converted
    }
)
"""

    print(code_example)
    print('✅ Benefits of the new way:')
    print('   • No protobuf knowledge required')
    print('   • Clean, readable code')
    print('   • Automatic type conversion')
    print('   • Better developer experience')
    print('   • Backward compatible with pre-wrapped objects')


def test_real_example():
    """Test the new functionality with a real example."""
    print('\n🚀 REAL EXAMPLE:')
    print('=' * 50)

    try:
        with DaprClient() as client:
            inputs = [
                ConversationInput(
                    content="What's the weather like today? Use the weather tool if available.",
                    role='user',
                )
            ]

            print('📤 Sending request with simple parameters...')

            # This is the new, simple way - no protobuf knowledge needed!
            response = client.converse_alpha1(
                name='echo',  # Using echo component for testing
                inputs=inputs,
                parameters={
                    'tool_choice': 'auto',
                    'temperature': 0.7,
                    'max_tokens': 1000,
                    'stream': False,
                    'top_p': 0.9,
                    'frequency_penalty': 0.0,
                    'presence_penalty': 0.0,
                },
            )

            print(f'✅ Success! Received {len(response.outputs)} outputs')

            for i, output in enumerate(response.outputs):
                print(f'   Output {i+1}: {output.result[:100]}...')

            if response.usage:
                print(f'📊 Usage: {response.usage.total_tokens} tokens')

    except Exception as e:
        print(f'⚠️  Test failed (expected if Dapr not running): {e}')


def test_backward_compatibility():
    """Test that pre-wrapped protobuf objects still work."""
    print('\n🔄 BACKWARD COMPATIBILITY TEST:')
    print('=' * 50)

    try:
        from google.protobuf.any_pb2 import Any as ProtobufAny
        from google.protobuf.wrappers_pb2 import StringValue

        # Create a pre-wrapped parameter (old way)
        pre_wrapped_any = ProtobufAny()
        pre_wrapped_any.Pack(StringValue(value='auto'))

        with DaprClient() as client:
            inputs = [ConversationInput(content='Test backward compatibility', role='user')]

            # Mix of old (pre-wrapped) and new (raw) parameters
            response = client.converse_alpha1(
                name='echo',
                inputs=inputs,
                parameters={
                    'tool_choice': pre_wrapped_any,  # Old way (pre-wrapped)
                    'temperature': 0.8,  # New way (raw value)
                    'max_tokens': 500,  # New way (raw value)
                },
            )

            print('✅ Backward compatibility test passed!')
            print('   Mixed parameters (old + new) work correctly')

    except Exception as e:
        print(f'⚠️  Backward compatibility test failed: {e}')


def main():
    """Run the demonstration."""
    print('🎯 Conversation API Parameter Conversion Demo')
    print('=' * 60)

    demonstrate_old_way()
    demonstrate_new_way()
    test_real_example()
    test_backward_compatibility()

    print('\n🎉 Demo completed!')
    print('\nKey takeaways:')
    print('• Developers can now use raw Python values in parameters')
    print('• No more manual protobuf wrapping required')
    print('• Backward compatibility is maintained')
    print('• Much better developer experience!')


if __name__ == '__main__':
    main()
