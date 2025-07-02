#!/usr/bin/env python3

"""
Working Multi-turn Tool Calling Example

Based on the structure from TestMultiTurnWithOpenAIRealData in the echo component.
This demonstrates the correct conversation flow for multi-turn tool calling.
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


def debug_conversation_input(input_obj, step_name):
    """Debug helper to show the exact structure being sent"""
    print(f"\n🔍 DEBUG - {step_name}")
    print("-" * 40)

    # Convert to dict for JSON serialization
    debug_dict = {
        "role": input_obj.role,
        "parts": []
    }

    for i, part in enumerate(input_obj.parts):
        part_dict = {"part_index": i}

        if part.text:
            part_dict["type"] = "text"
            part_dict["content"] = part.text.text
        elif part.tool_call:
            part_dict["type"] = "tool_call"
            part_dict["content"] = {
                "type": "tool_call",
                "id": part.tool_call.id,
                "name": part.tool_call.name,
                "arguments": part.tool_call.arguments
            }
        elif part.tool_result:
            part_dict["type"] = "tool_result"
            part_dict["content"] = {
                "type": "tool_result",
                "tool_call_id": part.tool_result.tool_call_id,
                "name": part.tool_result.name,
                "content": part.tool_result.content
            }

        debug_dict["parts"].append(part_dict)

    print(json.dumps(debug_dict, indent=2))
    print("-" * 40)

async def main():
    """Demonstrate working multi-turn tool calling based on echo component test patterns"""

    print("🔧 WORKING MULTI-TURN TOOL CALLING WITH DEBUG")
    print("=" * 50)
    print("Based on TestMultiTurnWithOpenAIRealData pattern")

    async with DaprGrpcClientAsync() as client:
        # Define weather tool using new flat structure
        weather_tool = Tool(
            type="function",
            name="get_weather",
            description="Get current weather in a location",
            parameters='{"type": "object", "properties": {"location": {"type": "string", "description": "City name"}}, "required": ["location"]}'
        )

        print("\\n📝 Step 1: User asks question (tools passed at request level)")
        # Step 1: User message (tools now passed at request level)
        user_message = ConversationInput(
            role="user",
            parts=[
                ContentPart(text=TextContent(text="What's the weather like in San Francisco? I'm deciding what to wear today."))
            ]
        )

        print("   User: What's the weather like in San Francisco? I'm deciding what to wear today.")
        print("   Tools: 1 tool passed at request level")

        # Debug the user message structure
        debug_conversation_input(user_message, "User Message")

        # Make first request to get tool calls (tools passed at request level)
        print("\\n🤖 Making request to OpenAI...")
        try:
            response1 = await client.converse_alpha1(
                name="openai",
                inputs=[user_message],
                tools=[weather_tool]
            )

            print(f"   Response: {response1.outputs[0].result}")
            print(f"   Finish reason: {response1.outputs[0].finish_reason}")

            # Extract tool calls from response
            tool_calls = response1.outputs[0].get_tool_calls()
            print(f"   Tool calls: {len(tool_calls)} generated")

            if tool_calls:
                print("\\n🔄 Step 2: Processing tool calls...")

                # Build conversation history following the test pattern
                conversation_history = [
                    user_message,  # Original user message
                    # Add assistant response with tool calls
                    ConversationInput(
                        role="assistant",
                        parts=response1.outputs[0].parts  # Use actual response parts
                    )
                ]

                # Debug the assistant message with tool calls
                debug_conversation_input(conversation_history[1], "Assistant Message with Tool Calls")

                # Step 3: Add tool results (simulate tool execution)
                for tool_call in tool_calls:
                    if tool_call.name == "get_weather":
                        # Simulate weather API response (same as test)
                        tool_result = '{"temperature": 65, "condition": "partly cloudy", "humidity": 70, "wind": "10 mph W", "feels_like": 68}'
                    else:
                        tool_result = '{"result": "success", "message": "Tool executed successfully"}'

                    print(f"   Tool {tool_call.name} -> {tool_result[:50]}...")

                    # Add tool result to conversation
                    tool_result_input = ConversationInput(
                        role="tool",
                        parts=[
                            ContentPart(tool_result=ToolResultContent(
                                tool_call_id=tool_call.id,
                                name=tool_call.name,
                                content=tool_result,
                                is_error=False
                            ))
                        ]
                    )
                    conversation_history.append(tool_result_input)

                    # Debug the tool result message
                    debug_conversation_input(tool_result_input, f"Tool Result Message ({tool_call.name})")

                # Step 4: Add user follow-up (exactly like the test)
                follow_up_message = ConversationInput(
                    role="user",
                    parts=[
                        ContentPart(text=TextContent(text="Thanks! Based on that weather, what should I wear?"))
                    ]
                )
                conversation_history.append(follow_up_message)

                print("\\n👤 Step 3: User follow-up question")
                print("   User: Thanks! Based on that weather, what should I wear?")

                # Debug the follow-up message
                debug_conversation_input(follow_up_message, "User Follow-up Message")

                print(f"\\n🔄 Step 4: Sending complete conversation history ({len(conversation_history)} messages)")
                print("\\n🔍 COMPLETE CONVERSATION HISTORY DEBUG:")
                print("=" * 60)
                for i, msg in enumerate(conversation_history):
                    debug_conversation_input(msg, f"Message {i+1} ({msg.role})")
                print("=" * 60)

                # Make final request with complete conversation history (tools still available)
                response2 = await client.converse_alpha1(
                    name="openai",
                    inputs=conversation_history,
                    tools=[weather_tool]
                )

                print(f"\\n✅ Final Response: {response2.outputs[0].result}")
                print(f"   Finish reason: {response2.outputs[0].finish_reason}")

                if response2.usage:
                    print(f"   Usage: {response2.usage.total_tokens} tokens")

                print("\\n🎉 MULTI-TURN TOOL CALLING SUCCESSFUL!")
                print("   ✅ Tools provided at request level")
                print("   ✅ Tool calls generated")
                print("   ✅ Tool results processed")
                print("   ✅ Contextual follow-up handled")

            else:
                print("\\n❌ No tool calls generated - check tool definitions")

        except Exception as e:
            print(f"\\n❌ Error: {e}")
            print("\\nThis demonstrates the correct structure even if the request fails.")
            print("The issue is likely in the Dapr conversation component, not the Python SDK.")

if __name__ == "__main__":
    asyncio.run(main())
