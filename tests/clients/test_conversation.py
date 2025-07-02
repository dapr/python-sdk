#!/usr/bin/env python3

"""
Comprehensive tests for Dapr conversation API functionality.

This test suite covers:
- Basic conversation API
- Streaming conversation API
- Tool calling functionality
- NEW: Content parts-based architecture
- Error handling
- Both sync and async implementations
- Backward compatibility
"""

import asyncio
import json
import unittest

from google.rpc import code_pb2, status_pb2

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc._request import (
    ContentPart,
    ConversationInput,
    TextContent,
    Tool,
    ToolCallContent,
    ToolResultContent,
)
from tests.clients.fake_dapr_server import FakeDaprSidecar


class ConversationTestBase:
    """Base class for conversation tests with common setup."""

    grpc_port = 50001
    http_port = 3500
    scheme = ''

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls.grpc_port, http_port=cls.http_port)
        cls._fake_dapr_server.start()

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()

    def create_weather_tool(self):
        """Create a weather tool for testing (new simplified structure)."""
        return Tool(
            type='function',
            name='get_weather',
            description='Get weather information for a location',
            parameters=json.dumps({
                'type': 'object',
                'properties': {
                    'location': {
                        'type': 'string',
                        'description': 'The city and state, e.g. San Francisco, CA'
                    },
                    'unit': {
                        'type': 'string',
                        'enum': ['celsius', 'fahrenheit'],
                        'description': 'Temperature unit'
                    }
                },
                'required': ['location']
            })
        )

    def create_weather_tool_legacy(self):
        """Create a weather tool for testing (legacy structure)."""
        return Tool(
            type='function',
            function=ToolFunction(
                name='get_weather',
                description='Get weather information for a location',
                parameters=json.dumps({
                    'type': 'object',
                    'properties': {
                        'location': {
                            'type': 'string',
                            'description': 'The city and state, e.g. San Francisco, CA'
                        },
                        'unit': {
                            'type': 'string',
                            'enum': ['celsius', 'fahrenheit'],
                            'description': 'Temperature unit'
                        }
                    },
                    'required': ['location']
                })
            )
        )

    def create_calculate_tool(self):
        """Create a calculate tool for testing (new simplified structure)."""
        return Tool(
            type='function',
            name='calculate',
            description='Perform mathematical calculations',
            parameters=json.dumps({
                'type': 'object',
                'properties': {
                    'expression': {
                        'type': 'string',
                        'description': 'Mathematical expression to evaluate'
                    }
                },
                'required': ['expression']
            })
        )


class ConversationSyncTests(ConversationTestBase, unittest.TestCase):
    """Synchronous conversation API tests."""

    def test_basic_conversation(self):
        """Test basic conversation functionality."""
        with DaprClient() as client:
            inputs = [
                ConversationInput(content='Hello', role='user'),
                ConversationInput(content='How are you?', role='user'),
            ]

            response = client.converse_alpha1(name='test-llm', inputs=inputs)

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 2)
            self.assertIn('Hello', response.outputs[0].result)
            self.assertIn('How are you?', response.outputs[1].result)
            self.assertIsNotNone(response.context_id)
            self.assertIsNotNone(response.usage)

    def test_conversation_with_options(self):
        """Test conversation with various options."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Hello with options', role='user', scrub_pii=True)]

            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                context_id='test-context-123',
                temperature=0.7,
                scrub_pii=True,
                metadata={'test_key': 'test_value'}
            )

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)
            self.assertEqual(response.context_id, 'test-context-123')

    def test_tool_calling_weather(self):
        """Test tool calling with weather tool."""
        with DaprClient() as client:
            weather_tool = self.create_weather_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='What is the weather in San Francisco?'))
                ]
            )]

            response = client.converse_alpha1(name='test-llm', inputs=inputs, tools=[weather_tool])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

            output = response.outputs[0]
            tool_calls = output.get_tool_calls()
            self.assertIsNotNone(tool_calls)
            self.assertEqual(len(tool_calls), 1)

            tool_call = tool_calls[0]
            self.assertEqual(tool_call.name, 'get_weather')
            self.assertEqual(tool_call.type, 'function')
            self.assertIn('San Francisco', tool_call.arguments)
            self.assertEqual(output.finish_reason, 'tool_calls')

    def test_tool_calling_calculate(self):
        """Test tool calling with calculate tool."""
        with DaprClient() as client:
            calc_tool = self.create_calculate_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='Calculate 15 * 23'))
                ]
            )]

            response = client.converse_alpha1(name='test-llm', inputs=inputs, tools=[calc_tool])

            self.assertIsNotNone(response)
            output = response.outputs[0]
            tool_calls = output.get_tool_calls()
            self.assertIsNotNone(tool_calls)
            self.assertTrue(len(tool_calls) > 0)

            tool_call = tool_calls[0]
            self.assertEqual(tool_call.name, 'calculate')
            self.assertIn('15 * 23', tool_call.arguments)

    def test_tool_result_input(self):
        """Test sending tool result back to LLM."""
        with DaprClient() as client:
            tool_result = ToolResultContent(
                tool_call_id='call_123',
                name='get_weather',
                content='{"temperature": 72, "condition": "sunny", "humidity": 65}'
            )
            inputs = [ConversationInput.from_tool_result_simple(
                tool_name=tool_result.name,
                call_id=tool_result.tool_call_id,
                result=tool_result.content
            )]

            response = client.converse_alpha1(name='test-llm', inputs=inputs)

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)
            self.assertIn('tool result', response.outputs[0].result)
            self.assertEqual(response.outputs[0].finish_reason, 'stop')

    def test_multiple_tools(self):
        """Test conversation with multiple tools."""
        with DaprClient() as client:
            weather_tool = self.create_weather_tool()
            calc_tool = self.create_calculate_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='I need both weather and calculation'))
                ]
            )]

            response = client.converse_alpha1(name='test-llm', inputs=inputs,
                                              tools=[weather_tool, calc_tool])

            self.assertIsNotNone(response)
            # The fake server will only call the first matching tool
            output = response.outputs[0]
            self.assertIsNotNone(output.parts)
            # Check for tool calls in parts
            tool_call_found = False
            for part in output.parts:
                if part.tool_call:
                    tool_call_found = True
                    break
            self.assertTrue(tool_call_found)

    def test_streaming_basic(self):
        """Test basic streaming conversation."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Hello streaming world!', role='user')]

            chunks = []
            context_id = None
            usage = None

            for response in client.converse_stream_alpha1(
                name='test-llm',
                inputs=inputs,
                context_id='stream-test-123'
            ):
                if response.chunk:
                    # Extract text from chunk parts or fallback to deprecated content
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.text:
                                chunks.append(part.text.text)

                if response.complete:
                    context_id = response.complete.context_id
                    usage = response.complete.usage

            self.assertGreater(len(chunks), 0)
            full_response = ''.join(chunks)
            self.assertIn('Hello streaming world!', full_response)
            self.assertEqual(context_id, 'stream-test-123')
            self.assertIsNotNone(usage)

    def test_streaming_with_tools(self):
        """Test streaming conversation with tool calling."""
        with DaprClient() as client:
            weather_tool = self.create_weather_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='Stream me the weather please'))
                ]
            )]

            tool_calls_found = False
            chunks = []

            for response in client.converse_stream_alpha1(name='test-llm', inputs=inputs,
                                                          tools=[weather_tool]):
                if response.chunk:
                    # Check for tool calls in chunk parts
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.tool_call:
                                tool_calls_found = True
                                self.assertEqual(part.tool_call.name, 'get_weather')
                            elif part.text:
                                chunks.append(part.text.text)

            self.assertTrue(tool_calls_found)

    def test_streaming_outputs_functionality(self):
        """Test new streaming outputs functionality with tool calls."""
        with DaprClient() as client:
            weather_tool = self.create_weather_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='Stream me the weather with outputs'))
                ]
            )]

            tool_calls_found = False
            complete_response = None

            for response in client.converse_stream_alpha1(name='test-llm', inputs=inputs,
                                                          tools=[weather_tool]):
                if response.chunk:
                    # Check for tool calls in streaming chunks
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.tool_call:
                                tool_calls_found = True
                                self.assertEqual(part.tool_call.name, 'get_weather')

                if response.complete:
                    complete_response = response.complete

            # Verify we got tool calls during streaming (which is what outputs functionality is about)
            self.assertTrue(tool_calls_found)

            # Verify complete response exists
            self.assertIsNotNone(complete_response)

            # Check if outputs field exists (it may be None if no tool calls)
            # The outputs field should be available even if empty
            if hasattr(complete_response, 'outputs'):
                self.assertIsInstance(complete_response.outputs, (list, type(None)))

    def test_conversation_stream_complete_outputs(self):
        """Test the new ConversationStreamComplete outputs field functionality."""
        from dapr.clients.grpc._response import (
            ConversationResult,
            ConversationStreamComplete,
            ConversationUsage,
        )

        # Test creating a ConversationStreamComplete with outputs
        usage = ConversationUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        # Create some mock outputs (tool calls that would be accumulated)
        outputs = [
            ConversationResult(
                result="Tool call result 1",
                finish_reason="tool_calls"
            ),
            ConversationResult(
                result="Tool call result 2",
                finish_reason="stop"
            )
        ]

        complete = ConversationStreamComplete(
            context_id="test-context",
            usage=usage,
            outputs=outputs
        )

        # Verify the outputs field exists and works
        self.assertEqual(complete.context_id, "test-context")
        self.assertIsNotNone(complete.usage)
        self.assertIsNotNone(complete.outputs)
        self.assertEqual(len(complete.outputs), 2)
        self.assertEqual(complete.outputs[0].result, "Tool call result 1")
        self.assertEqual(complete.outputs[1].finish_reason, "stop")

    def test_streaming_with_options(self):
        """Test streaming with various options."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Stream with options', role='user', scrub_pii=True)]

            chunks = []
            for response in client.converse_stream_alpha1(
                name='test-llm',
                inputs=inputs,
                context_id='options-stream-test',
                temperature=0.8,
                scrub_pii=True,
                metadata={'stream_test': 'true'}
            ):
                if response.chunk:
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.text:
                                chunks.append(part.text.text)

            self.assertGreater(len(chunks), 0)

    def test_conversation_error_handling(self):
        """Test conversation error handling."""
        # Test with fake server error
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Test error')
        )

        with DaprClient() as client:
            inputs = [ConversationInput(content='Error test', role='user')]

            with self.assertRaises(DaprGrpcError) as context:
                client.converse_alpha1(name='test-llm', inputs=inputs)
            self.assertIn('Test error', str(context.exception))

    def test_streaming_error_handling(self):
        """Test streaming conversation error handling."""
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Stream test error')
        )

        with DaprClient() as client:
            inputs = [ConversationInput(content='Stream error test', role='user')]

            with self.assertRaises(DaprGrpcError) as context:
                list(client.converse_stream_alpha1(name='test-llm', inputs=inputs))
            self.assertIn('Stream test error', str(context.exception))

    def test_empty_inputs_validation(self):
        """Test validation with empty inputs."""
        with DaprClient() as client:
            # The client doesn't actually validate empty inputs,
            # it will send the request to the server which should handle it
            response = client.converse_alpha1(name='test-llm', inputs=[])
            self.assertIsNotNone(response)

            # For streaming, empty inputs will just result in no chunks
            chunks = list(client.converse_stream_alpha1(name='test-llm', inputs=[]))
            # Should get at least the completion chunk
            self.assertGreaterEqual(len(chunks), 1)


class ConversationAsyncTests(ConversationTestBase, unittest.IsolatedAsyncioTestCase):
    """Asynchronous conversation API tests."""

    async def test_basic_async_conversation(self):
        """Test basic async conversation functionality."""
        async with AsyncDaprClient() as client:
            inputs = [
                ConversationInput(content='Hello async', role='user'),
                ConversationInput(content='How are you async?', role='user'),
            ]

            response = await client.converse_alpha1(name='test-llm', inputs=inputs)

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 2)
            self.assertIn('Hello async', response.outputs[0].result)
            self.assertIn('How are you async?', response.outputs[1].result)

    async def test_async_conversation_with_options(self):
        """Test async conversation with various options."""
        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='Async with options', role='user')]

            response = await client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                context_id='async-context-123',
                temperature=0.9,
                scrub_pii=False,
                metadata={'async_test': 'true'}
            )

            self.assertIsNotNone(response)
            self.assertEqual(response.context_id, 'async-context-123')

    async def test_async_tool_calling(self):
        """Test async tool calling."""
        async with AsyncDaprClient() as client:
            weather_tool = self.create_weather_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='Async weather request for Tokyo'))
                ]
            )]

            response = await client.converse_alpha1(name='test-llm', inputs=inputs,
                                                    tools=[weather_tool])

            self.assertIsNotNone(response)
            output = response.outputs[0]
            tool_calls = output.get_tool_calls()
            self.assertIsNotNone(tool_calls)
            self.assertTrue(len(tool_calls) > 0)

            tool_call = tool_calls[0]
            self.assertEqual(tool_call.name, 'get_weather')
            self.assertEqual(output.finish_reason, 'tool_calls')

    async def test_async_streaming_basic(self):
        """Test basic async streaming conversation."""
        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='Hello async streaming!', role='user')]

            chunks = []
            context_id = None
            usage = None

            async for response in client.converse_stream_alpha1(
                name='test-llm',
                inputs=inputs,
                context_id='async-stream-123'
            ):
                if response.chunk:
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.text:
                                chunks.append(part.text.text)

                if response.complete:
                    context_id = response.complete.context_id
                    usage = response.complete.usage

            self.assertGreater(len(chunks), 0)
            full_response = ''.join(chunks)
            self.assertIn('Hello async streaming!', full_response)
            self.assertEqual(context_id, 'async-stream-123')
            self.assertIsNotNone(usage)

    async def test_async_streaming_with_tools(self):
        """Test async streaming with tool calling."""
        async with AsyncDaprClient() as client:
            calc_tool = self.create_calculate_tool()

            inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='Async calculate 42 + 58'))
                ]
            )]

            tool_calls_found = False
            async for response in client.converse_stream_alpha1(name='test-llm', inputs=inputs,
                                                                tools=[calc_tool]):
                if response.chunk:
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.tool_call:
                                tool_calls_found = True
                                self.assertEqual(part.tool_call.name, 'calculate')

            self.assertTrue(tool_calls_found)

    async def test_concurrent_async_conversations(self):
        """Test multiple concurrent async conversations."""
        async with AsyncDaprClient() as client:
            async def run_conversation(message, session_id):
                inputs = [ConversationInput(content=message, role='user')]
                response = await client.converse_alpha1(
                    name='test-llm',
                    inputs=inputs,
                    context_id=session_id
                )
                return response.outputs[0].result

            # Run 3 conversations concurrently
            tasks = [
                run_conversation('First concurrent message', 'concurrent-1'),
                run_conversation('Second concurrent message', 'concurrent-2'),
                run_conversation('Third concurrent message', 'concurrent-3'),
            ]

            results = await asyncio.gather(*tasks)

            self.assertEqual(len(results), 3)
            for i, result in enumerate(results, 1):
                expected_words = ['First', 'Second', 'Third'][i-1]
                self.assertIn(expected_words, result)

    async def test_concurrent_async_streaming(self):
        """Test multiple concurrent async streaming conversations."""
        async with AsyncDaprClient() as client:
            async def stream_conversation(message, session_id):
                inputs = [ConversationInput(content=message, role='user')]
                chunks = []
                async for response in client.converse_stream_alpha1(
                    name='test-llm',
                    inputs=inputs,
                    context_id=session_id
                ):
                    if response.chunk:
                        if response.chunk.parts:
                            for part in response.chunk.parts:
                                if part.text:
                                    chunks.append(part.text.text)
                return ''.join(chunks)

            # Run 3 streaming conversations concurrently
            tasks = [
                stream_conversation('Stream one', 'stream-1'),
                stream_conversation('Stream two', 'stream-2'),
                stream_conversation('Stream three', 'stream-3'),
            ]

            results = await asyncio.gather(*tasks)

            self.assertEqual(len(results), 3)
            for result in results:
                self.assertIn('Stream', result)

    async def test_async_error_handling(self):
        """Test async conversation error handling."""
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Async test error')
        )

        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='Async error test', role='user')]

            with self.assertRaises(DaprGrpcError) as context:
                await client.converse_alpha1(name='test-llm', inputs=inputs)
            self.assertIn('Async test error', str(context.exception))

    async def test_async_streaming_error_handling(self):
        """Test async streaming error handling."""
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Async stream error')
        )

        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='Async stream error test', role='user')]

            with self.assertRaises(DaprGrpcError) as context:
                chunks = []
                async for response in client.converse_stream_alpha1(name='test-llm', inputs=inputs):
                    chunks.append(response)
            self.assertIn('Async stream error', str(context.exception))


class ConversationToolCallWorkflowTests(ConversationTestBase, unittest.TestCase):
    """Tests for complete tool calling workflows."""

    def test_complete_tool_calling_workflow(self):
        """Test a complete tool calling workflow: request -> tool call -> tool result -> final response."""
        with DaprClient() as client:
            # Step 1: Send initial request with tools
            weather_tool = self.create_weather_tool()

            initial_inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='What is the weather in San Francisco?'))
                ]
            )]

            response1 = client.converse_alpha1(name='test-llm', inputs=initial_inputs,
                                               tools=[weather_tool])

            # Verify tool call was made
            output = response1.outputs[0]
            tool_calls = output.get_tool_calls()  # Use helper method for backward compatibility
            self.assertIsNotNone(tool_calls)
            self.assertTrue(len(tool_calls) > 0)
            tool_call = tool_calls[0]
            self.assertEqual(tool_call.name, 'get_weather')

            # Step 2: Send tool result back
            tool_result = ToolResultContent(
                tool_call_id=tool_call.id,
                name='get_weather',
                content='{"temperature": 68, "condition": "partly cloudy", "humidity": 72}'
            )
            tool_result_inputs = [ConversationInput.from_tool_result_simple(
                tool_name=tool_result.name,
                call_id=tool_result.tool_call_id,
                result=tool_result.content
            )]

            response2 = client.converse_alpha1(name='test-llm', inputs=tool_result_inputs)

            # Verify final response
            self.assertIsNotNone(response2.outputs[0].result)
            self.assertIn('tool result', response2.outputs[0].result)
            self.assertEqual(response2.outputs[0].finish_reason, 'stop')

    def test_streaming_tool_calling_workflow(self):  # noqa: C901
        """Test a complete streaming tool calling workflow."""
        with DaprClient() as client:
            # Step 1: Stream initial request with tools
            calc_tool = self.create_calculate_tool()

            initial_inputs = [ConversationInput(
                role='user',
                parts=[
                    ContentPart(text=TextContent(text='Calculate the result of 25 * 4'))
                ]
            )]

            tool_call_id = None
            tool_calls_found = False

            for response in client.converse_stream_alpha1(
                name='test-llm', inputs=initial_inputs, tools=[calc_tool]):
                if response.chunk:
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.tool_call:
                                tool_calls_found = True
                                tool_call_id = part.tool_call.id
                                self.assertEqual(part.tool_call.name, 'calculate')

            self.assertTrue(tool_calls_found)
            self.assertIsNotNone(tool_call_id)

            # Step 2: Stream tool result back
            tool_result = ToolResultContent(
                tool_call_id=tool_call_id,
                name='calculate',
                content='{"result": 100}'
            )
            tool_result_inputs = [ConversationInput.from_tool_result_simple(
                tool_name=tool_result.name,
                call_id=tool_result.tool_call_id,
                result=tool_result.content
            )]

            final_chunks = []
            for response in client.converse_stream_alpha1(name='test-llm',
                                                          inputs=tool_result_inputs,
                                                          tools=[calc_tool]):
                if response.chunk:
                    if response.chunk.parts:
                        for part in response.chunk.parts:
                            if part.text:
                                final_chunks.append(part.text.text)

            final_response = ''.join(final_chunks)
            self.assertIn('tool result', final_response)


class ConversationContentPartsTests(ConversationTestBase, unittest.TestCase):
    """Tests for the new content parts-based architecture."""

    def test_text_content_part(self):
        """Test creating conversation input with text content part."""
        with DaprClient() as client:
            text_input = ConversationInput.from_text("Hello world", role="user")

            self.assertEqual(text_input.role, "user")
            self.assertIsNotNone(text_input.parts)
            self.assertEqual(len(text_input.parts), 1)
            self.assertIsNotNone(text_input.parts[0].text)
            self.assertEqual(text_input.parts[0].text.text, "Hello world")

            response = client.converse_alpha1(name='test-llm', inputs=[text_input])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    def test_tool_definitions_content_part(self):
        """Test that tools are now passed at request level, not as content parts."""
        with DaprClient() as client:
            weather_tool = self.create_weather_tool()
            calc_tool = self.create_calculate_tool()

            # Tools are now passed at the request level
            inputs = [ConversationInput.from_text("Tell me about tools", role="user")]

            # This should work - tools passed to the API call
            response = client.converse_alpha1(name='test-llm', inputs=inputs,
                                              tools=[weather_tool, calc_tool])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    def test_tool_call_content_part(self):
        """Test creating conversation input with tool call content part (new flat structure)."""
        tool_call = ToolCallContent(
            id="call_123",
            type="function",
            name="get_weather",
            arguments='{"location": "San Francisco", "unit": "celsius"}'
        )

        assistant_input = ConversationInput.from_tool_call(tool_call)

        self.assertEqual(assistant_input.role, "assistant")
        self.assertIsNotNone(assistant_input.parts)
        self.assertEqual(len(assistant_input.parts), 1)
        self.assertIsNotNone(assistant_input.parts[0].tool_call)
        self.assertEqual(assistant_input.parts[0].tool_call.id, "call_123")
        self.assertEqual(assistant_input.parts[0].tool_call.name, "get_weather")

    def test_tool_call_content_flat_structure(self):
        """Test that ToolCallContent supports the new flat structure matching protobuf."""
        # Test the flat structure that matches the actual protobuf
        from dapr.clients.grpc._response import ToolCallContent as ResponseToolCallContent

        # This should work with the flat structure
        tool_call = ResponseToolCallContent(
            id="call_456",
            type="function",
            name="calculate",
            arguments='{"expression": "10 + 5"}'
        )

        self.assertEqual(tool_call.id, "call_456")
        self.assertEqual(tool_call.type, "function")
        self.assertEqual(tool_call.name, "calculate")
        self.assertEqual(tool_call.arguments, '{"expression": "10 + 5"}')

        # Test that the flat structure works correctly
        # This is the expected flat structure instead of nested function.name/function.arguments
        self.assertIsInstance(tool_call.name, str)
        self.assertIsInstance(tool_call.arguments, str)

    def test_tool_result_content_part(self):
        """Test creating conversation input with tool result content part."""
        tool_result = ToolResultContent(
            tool_call_id="call_123",
            name="get_weather",
            content='{"temperature": 22, "condition": "sunny"}'
        )

        result_input = ConversationInput.from_tool_result_simple(
            tool_name=tool_result.name,
            call_id=tool_result.tool_call_id,
            result=tool_result.content
        )

        self.assertEqual(result_input.role, "tool")
        self.assertIsNotNone(result_input.parts)
        self.assertEqual(len(result_input.parts), 1)
        self.assertIsNotNone(result_input.parts[0].tool_result)
        self.assertEqual(result_input.parts[0].tool_result.tool_call_id, "call_123")
        self.assertEqual(result_input.parts[0].tool_result.name, "get_weather")

    def test_mixed_content_parts(self):
        """Test conversation input with multiple content parts (text only now)."""
        # With the new architecture, tools are passed at request level
        # Content parts now only contain text, tool calls, and tool results

        mixed_input = ConversationInput(
            role="user",
            parts=[
                ContentPart(text=TextContent(text="What's the weather in Paris?"))
            ]
        )

        self.assertEqual(mixed_input.role, "user")
        self.assertEqual(len(mixed_input.parts), 1)
        self.assertIsNotNone(mixed_input.parts[0].text)

    def test_multi_turn_tool_calling_workflow(self):
        """Test complete multi-turn tool calling workflow with content parts."""
        with DaprClient() as client:
            # Step 1: User message with tools passed at request level
            weather_tool = self.create_weather_tool()
            user_input = ConversationInput(
                role="user",
                parts=[
                    ContentPart(text=TextContent(text="What's the weather in Tokyo?"))
                ]
            )

            response = client.converse_alpha1(name='test-llm', inputs=[user_input],
                                              tools=[weather_tool])

            # Should get tool calls back
            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

            # Extract tool calls from response parts
            tool_calls = []
            for output in response.outputs:
                if output.parts:
                    for part in output.parts:
                        if part.tool_call:
                            tool_calls.append(part.tool_call)

                # Fallback to old structure
                if not tool_calls:
                    tool_calls = output.get_tool_calls()

            self.assertTrue(len(tool_calls) > 0)

            # Step 2: Create assistant message with tool calls
            assistant_input = ConversationInput(
                role="assistant",
                parts=[ContentPart(tool_call=tool_call) for tool_call in tool_calls]
            )

            # Step 3: Create tool result messages
            tool_result_inputs = []
            for tool_call in tool_calls:
                tool_result_inputs.append(ConversationInput.from_tool_result_simple(
                    tool_name=tool_call.name,
                    call_id=tool_call.id,
                    result='{"temperature": 18, "condition": "cloudy", "humidity": 75}'
                ))

            # Step 4: Complete conversation with history
            conversation_history = [user_input, assistant_input] + tool_result_inputs

            final_response = client.converse_alpha1(name='test-llm', inputs=conversation_history)

            self.assertIsNotNone(final_response)
            self.assertEqual(len(final_response.outputs), len(conversation_history))

    def test_backward_compatibility_with_content_parts(self):
        """Test that old-style inputs still work with new content parts system."""
        with DaprClient() as client:
            # Old style input
            old_input = ConversationInput(content="Hello", role="user")

            # New style input
            new_input = ConversationInput.from_text("Hello", role="user")

            # Both should work
            old_response = client.converse_alpha1(name='test-llm', inputs=[old_input])
            new_response = client.converse_alpha1(name='test-llm', inputs=[new_input])

            self.assertIsNotNone(old_response)
            self.assertIsNotNone(new_response)
            self.assertEqual(len(old_response.outputs), 1)
            self.assertEqual(len(new_response.outputs), 1)

    def test_response_content_parts_extraction(self):
        """Test extracting content from response parts."""
        with DaprClient() as client:
            weather_tool = self.create_weather_tool()

            inputs = [ConversationInput(
                role="user",
                parts=[
                    ContentPart(text=TextContent(text="What's the weather?"))
                ]
            )]

            response = client.converse_alpha1(name='test-llm', inputs=inputs, tools=[weather_tool])

            for output in response.outputs:
                # Test helper methods
                text = output.get_text()
                tool_calls = output.get_tool_calls()

                # Should get either text or tool calls
                self.assertTrue(text is not None or len(tool_calls) > 0)


class ConversationContentPartsAsyncTests(ConversationTestBase, unittest.IsolatedAsyncioTestCase):
    """Async tests for the new content parts-based architecture."""

    async def test_async_text_content_part(self):
        """Test async conversation with text content part."""
        async with AsyncDaprClient() as client:
            text_input = ConversationInput.from_text("Hello async world", role="user")

            response = await client.converse_alpha1(name='test-llm', inputs=[text_input])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    async def test_async_multi_turn_tool_calling(self):
        """Test async multi-turn tool calling with content parts."""
        async with AsyncDaprClient() as client:
            calc_tool = self.create_calculate_tool()

            # User message with tools passed at request level
            user_input = ConversationInput(
                role="user",
                parts=[
                    ContentPart(text=TextContent(text="Calculate 42 * 7"))
                ]
            )

            response = await client.converse_alpha1(name='test-llm', inputs=[user_input],
                                                    tools=[calc_tool])

            # Extract tool calls
            tool_calls = []
            for output in response.outputs:
                if output.parts:
                    for part in output.parts:
                        if part.tool_call:
                            tool_calls.append(part.tool_call)
                if not tool_calls:
                    tool_calls = output.get_tool_calls()

            if tool_calls:
                # Create assistant message with tool calls
                assistant_input = ConversationInput.from_tool_call(tool_calls[0])

                # Create tool result
                tool_result = ToolResultContent(
                    tool_call_id=tool_calls[0].id,
                    name=tool_calls[0].name,
                    content="294"
                )
                result_input = ConversationInput.from_tool_result_simple(
                    tool_name=tool_result.name,
                    call_id=tool_result.tool_call_id,
                    result=tool_result.content
                )

                # Complete conversation
                final_response = await client.converse_alpha1(
                    name='test-llm',
                    inputs=[user_input, assistant_input, result_input]
                )

                self.assertIsNotNone(final_response)

    async def test_async_streaming_with_content_parts(self):
        """Test async streaming with content parts."""
        async with AsyncDaprClient() as client:
            text_input = ConversationInput.from_text("Tell me a story", role="user")

            chunks = []
            async for response in client.converse_stream_alpha1(name='test-llm',
                                                                inputs=[text_input]):
                chunks.append(response)

            self.assertTrue(len(chunks) > 0)


class ConversationParameterConversionTests(ConversationTestBase, unittest.TestCase):
    """Tests for automatic parameter conversion in conversation API."""

    def test_parameter_conversion_sync_basic(self):
        """Test basic parameter conversion with sync client."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Test with parameters', role='user')]

            # Test with raw Python parameters - should not raise protobuf errors
            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "stream": False,
                    "top_p": 0.9,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                }
            )

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    def test_parameter_conversion_sync_streaming(self):
        """Test parameter conversion with sync streaming."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Stream with parameters', role='user')]

            chunks = []
            for response in client.converse_stream_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "tool_choice": "auto",
                    "temperature": 0.8,
                    "max_tokens": 500,
                    "stream": True,
                }
            ):
                chunks.append(response)
                if len(chunks) >= 3:  # Limit for test performance
                    break

            self.assertTrue(len(chunks) > 0)

    def test_parameter_conversion_backward_compatibility(self):
        """Test that pre-wrapped protobuf parameters still work."""
        from google.protobuf.any_pb2 import Any as GrpcAny
        from google.protobuf.wrappers_pb2 import StringValue

        # Create pre-wrapped parameter (old way)
        pre_wrapped_any = GrpcAny()
        pre_wrapped_any.Pack(StringValue(value="auto"))

        with DaprClient() as client:
            inputs = [ConversationInput(content='Backward compatibility test', role='user')]

            # Mix of old (pre-wrapped) and new (raw) parameters
            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "tool_choice": pre_wrapped_any,  # Old way (pre-wrapped)
                    "temperature": 0.8,              # New way (raw value)
                    "max_tokens": 500,               # New way (raw value)
                }
            )

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    def test_parameter_conversion_realistic_openai(self):
        """Test with realistic OpenAI-style parameters."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='OpenAI style test', role='user')]

            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "top_p": 1.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                    "stream": False,
                    "tool_choice": "auto",
                }
            )

            self.assertIsNotNone(response)

    def test_parameter_conversion_realistic_anthropic(self):
        """Test with realistic Anthropic-style parameters."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Anthropic style test', role='user')]

            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 4096,
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "top_k": 250,
                    "stream": False,
                }
            )

            self.assertIsNotNone(response)

    def test_parameter_conversion_edge_cases(self):
        """Test parameter conversion with edge cases."""
        with DaprClient() as client:
            inputs = [ConversationInput(content='Edge cases test', role='user')]

            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "int32_max": 2147483647,    # Int32 maximum
                    "int64_large": 9999999999,  # Requires Int64
                    "negative_temp": -0.5,      # Negative float
                    "zero_value": 0,            # Zero integer
                    "false_flag": False,        # Boolean false
                    "true_flag": True,          # Boolean true
                    "empty_string": "",         # Empty string
                }
            )

            self.assertIsNotNone(response)


class ConversationParameterConversionAsyncTests(ConversationTestBase,
                                                unittest.IsolatedAsyncioTestCase):
    """Async tests for parameter conversion functionality."""

    async def test_parameter_conversion_async_basic(self):
        """Test basic parameter conversion with async client."""
        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='Async test with parameters', role='user')]

            response = await client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "stream": False,
                    "top_p": 0.9,
                }
            )

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    async def test_parameter_conversion_async_streaming(self):
        """Test parameter conversion with async streaming."""
        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='Async stream with parameters', role='user')]

            chunks = []
            async for response in client.converse_stream_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "tool_choice": "auto",
                    "temperature": 0.8,
                    "stream": True,
                }
            ):
                chunks.append(response)
                if len(chunks) >= 3:  # Limit for test performance
                    break

            self.assertTrue(len(chunks) > 0)

    async def test_parameter_conversion_async_json_streaming(self):
        """Test parameter conversion with async JSON streaming."""
        async with AsyncDaprClient() as client:
            inputs = [ConversationInput(content='JSON stream test', role='user')]

            chunks = []
            async for chunk_dict in client.converse_stream_json(
                name='test-llm',
                inputs=inputs,
                parameters={
                    "temperature": 0.9,
                    "max_tokens": 100,
                    "stream": True,
                }
            ):
                chunks.append(chunk_dict)
                if len(chunks) >= 2:  # Limit for test performance
                    break

            self.assertTrue(len(chunks) > 0)
            # Verify JSON structure
            for chunk in chunks:
                self.assertIsInstance(chunk, dict)
                self.assertIn('choices', chunk)

    async def test_parameter_conversion_async_concurrent(self):
        """Test parameter conversion with concurrent async requests."""
        async with AsyncDaprClient() as client:

            async def make_request(message, params):
                inputs = [ConversationInput(content=message, role='user')]
                return await client.converse_alpha1(
                    name='test-llm',
                    inputs=inputs,
                    parameters=params
                )

            # Run multiple concurrent requests with different parameters
            tasks = [
                make_request("Test 1", {"temperature": 0.1, "max_tokens": 100}),
                make_request("Test 2", {"temperature": 0.5, "max_tokens": 200}),
                make_request("Test 3", {"temperature": 0.9, "max_tokens": 300}),
            ]

            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                self.assertIsNotNone(response)
                self.assertEqual(len(response.outputs), 1)


if __name__ == '__main__':
    unittest.main()
