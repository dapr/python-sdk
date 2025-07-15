#!/usr/bin/env python3
"""
Multi-turn Tool Calling Example - Now with Content Parts Support!

This example demonstrates the NEW content parts-based architecture that supports
proper multi-turn tool calling workflows in the Dapr Python SDK.

The new architecture supports:
1. ✅ User messages with tool definitions
2. ✅ Assistant messages with tool calls
3. ✅ Tool result messages
4. ✅ Final assistant responses

This enables proper multi-turn conversations with LLMs that can call tools
and incorporate the results into their responses.
"""

import asyncio
import json

from dapr.aio.clients.grpc.client import DaprGrpcClientAsync
from dapr.clients.grpc._request import (
    ContentPart,
    ConversationInput,
    TextContent,
    Tool,
    ToolResultContent,
)


def get_weather(location: str, unit: str = 'celsius') -> str:
    """Mock weather function."""
    return f'The weather in {location} is 22°{unit[0].upper()} and sunny'


def calculate(expression: str) -> str:
    """Mock calculation function."""
    try:
        result = eval(expression)  # In real code, use a safe evaluator
        return str(result)
    except Exception as e:
        return f'Error: {e}'


# Tool definitions using new flat structure
WEATHER_TOOL = Tool(
    type='function',
    name='get_weather',
    description='Get the current weather in a given location',
    parameters=json.dumps(
        {
            'type': 'object',
            'properties': {
                'location': {
                    'type': 'string',
                    'description': 'The city and state, e.g. San Francisco, CA',
                },
                'unit': {
                    'type': 'string',
                    'enum': ['celsius', 'fahrenheit'],
                    'description': 'The unit for temperature',
                },
            },
            'required': ['location'],
        }
    ),
)

CALC_TOOL = Tool(
    type='function',
    name='calculate',
    description='Perform mathematical calculations',
    parameters=json.dumps(
        {
            'type': 'object',
            'properties': {
                'expression': {
                    'type': 'string',
                    'description': 'Mathematical expression to evaluate',
                }
            },
            'required': ['expression'],
        }
    ),
)


async def demonstrate_multi_turn_tool_calling():
    """Demonstrate multi-turn tool calling with the new content parts architecture."""

    print('🚀 Multi-turn Tool Calling with Content Parts')
    print('=' * 60)

    async with DaprGrpcClientAsync() as client:
        # Step 1: User message with question (tools passed at request level)
        print('📝 Step 1: User asks question with tools available')
        user_input = ConversationInput(
            role='user',
            parts=[
                ContentPart(
                    text=TextContent(text="What's the weather in Paris and what's 15 + 27?")
                ),
            ],
        )

        print("   User: What's the weather in Paris and what's 15 + 27?")
        print(f'   Tools available: {len([WEATHER_TOOL, CALC_TOOL])}')

        # Call LLM with tools passed at request level
        response = await client.converse_alpha1(
            name='openai',
            inputs=[user_input],
            tools=[WEATHER_TOOL, CALC_TOOL]
        )

        # Extract tool calls from response
        tool_calls = []
        assistant_text = None

        for output in response.outputs:
            if output.parts:
                for part in output.parts:
                    if part.tool_call:
                        tool_calls.append(part.tool_call)
                    elif part.text:
                        assistant_text = part.text.text

            # Fallback to old structure
            if not tool_calls:
                tool_calls = output.get_tool_calls()
            if not assistant_text:
                assistant_text = output.get_text()

        print(f"   Assistant: {assistant_text or 'Making tool calls...'}")
        print(f'   Tool calls: {len(tool_calls)}')

        if not tool_calls:
            print('   ❌ No tool calls detected - ending demo')
            return

        # Step 2: Create assistant message with tool calls for conversation history
        print('\n📋 Step 2: Assistant message with tool calls')
        assistant_input = ConversationInput(
            role='assistant', parts=[ContentPart(tool_call=tool_call) for tool_call in tool_calls]
        )

        # Step 3: Execute tools and create tool result messages
        print('\n🔧 Step 3: Execute tools and create result messages')
        tool_result_inputs = []

        for tool_call in tool_calls:
            # Handle both old and new tool call structures
            if hasattr(tool_call, 'function') and tool_call.function:
                # Old structure with nested function
                func_name = tool_call.function.name
                func_args = tool_call.function.arguments
            else:
                # New flat structure (may be implemented in future)
                func_name = tool_call.name
                func_args = getattr(tool_call, 'arguments', '{}')

            print(f'   Executing: {func_name}({func_args})')

            # Execute the tool
            if func_name == 'get_weather':
                args = json.loads(func_args)
                result = get_weather(**args)
            elif func_name == 'calculate':
                args = json.loads(func_args)
                result = calculate(**args)
            else:
                result = f'Unknown function: {func_name}'

            print(f'   Result: {result}')

            # Create tool result input
            tool_result_input = ConversationInput(
                role='tool',
                parts=[
                    ContentPart(
                        tool_result=ToolResultContent(
                            tool_call_id=tool_call.id, name=func_name, content=result
                        )
                    )
                ],
            )
            tool_result_inputs.append(tool_result_input)

        # Step 4: Multi-turn conversation with complete history
        print('\n💬 Step 4: Multi-turn conversation with complete history')

        # Build complete conversation history
        conversation_history = [
            user_input,  # Original user message with tools
            assistant_input,  # Assistant message with tool calls
            *tool_result_inputs,  # Tool result messages
        ]

        print(f'   Conversation history: {len(conversation_history)} messages')
        print('   - User message with question')
        print('   - Assistant message with tool calls')
        print(f'   - {len(tool_result_inputs)} tool result messages')

        # Get final response incorporating tool results (tools still available)
        final_response = await client.converse_alpha1(
            name='openai',
            inputs=conversation_history,
            tools=[WEATHER_TOOL, CALC_TOOL]
        )

        # Extract final response
        final_text = None
        for output in final_response.outputs:
            if output.parts:
                for part in output.parts:
                    if part.text:
                        final_text = part.text.text
                        break
            if not final_text:
                final_text = output.get_text()
            if final_text:
                break

        print('\n✅ Final Assistant Response:')
        print(f'   {final_text}')

        print('\n🎉 Multi-turn tool calling completed successfully!')
        print(f'   Context ID: {final_response.context_id}')


async def demonstrate_backward_compatibility():
    """Show that the new system is backward compatible with old code."""

    print('\n🔄 Backward Compatibility Demo')
    print('=' * 40)

    async with DaprGrpcClientAsync() as client:
        # Old style: using deprecated content field
        old_style_input = ConversationInput(content='Hello! What is 2 + 2?', role='user')

        print('📝 Old style input (deprecated content field)')
        print(f'   Content: {old_style_input.content}')

        response = await client.converse_alpha1(name='openai', inputs=[old_style_input])

        # Extract response (works with both old and new structure)
        for output in response.outputs:
            text = output.get_text()  # Helper method works with both
            if text:
                print(f'   Response: {text}')
                break

        print('✅ Backward compatibility confirmed!')


async def main():
    """Main demo function."""
    print('🌟 DAPR CONVERSATION API - MULTI-TURN TOOL CALLING DEMO')
    print('=' * 70)
    print()
    print('This demo shows the new content parts-based architecture that')
    print('enables proper multi-turn tool calling workflows.')
    print()

    try:
        await demonstrate_multi_turn_tool_calling()
        await demonstrate_backward_compatibility()

        print('\n' + '=' * 70)
        print('🎯 KEY FEATURES DEMONSTRATED:')
        print('✅ Content parts-based architecture')
        print('✅ Multi-turn tool calling workflow')
        print('✅ Complete conversation history support')
        print('✅ Tool definitions, calls, and results')
        print('✅ Backward compatibility with old API')
        print('✅ Assistant messages with tool calls')
        print('✅ Tool result messages')
        print()
        print('🚀 The Dapr Python SDK now supports full multi-turn tool calling!')

    except Exception as e:
        print(f'\n❌ Demo failed: {e}')
        print('\nThis is expected if:')
        print('- Dapr sidecar is not running')
        print('- OpenAI component is not configured')
        print("- The Dapr runtime doesn't support content parts yet")

        print('\n🔧 To run this demo:')
        print('1. Start Dapr sidecar: python tools/run_dapr_dev.py')
        print('2. Ensure OpenAI component is configured')
        print('3. Run this script: python examples/conversation/multi_turn_tool_calling_example.py')


if __name__ == '__main__':
    asyncio.run(main())
