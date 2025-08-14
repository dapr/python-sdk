#!/usr/bin/env python3

"""
Comprehensive tests for Dapr conversation API functionality.

This test suite covers:
- Basic conversation API (Alpha1)
- Advanced conversation API (Alpha2) with tool calling
- Multi-turn conversations
- Different message types (user, system, assistant, developer, tool)
- Error handling
- Both sync and async implementations
- Parameter conversion and validation
"""
import asyncio
import unittest
import uuid

from google.rpc import code_pb2, status_pb2

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc import conversation
from dapr.clients.grpc._conversation_helpers import (
    ToolArgumentError,
    ToolExecutionError,
)
from dapr.clients.grpc.conversation import (
    ConversationInput,
    ConversationInputAlpha2,
    ConversationMessage,
    ConversationMessageContent,
    ConversationMessageOfAssistant,
    ConversationMessageOfSystem,
    ConversationMessageOfTool,
    ConversationMessageOfUser,
    ConversationTools,
    ConversationToolsFunction,
    FunctionBackend,
    execute_registered_tool_async,
    get_registered_tools,
    register_tool,
    tool as tool_decorator,
    unregister_tool,
)
from dapr.conf import settings

from tests.clients.fake_dapr_server import FakeDaprSidecar


def create_weather_tool():
    """Create a weather tool for testing."""
    return ConversationTools(
        function=ConversationToolsFunction(
            name='get_weather',
            description='Get weather information for a location',
            parameters={
                'type': 'object',
                'properties': {
                    'location': {
                        'type': 'string',
                        'description': 'The city and state, e.g. San Francisco, CA',
                    },
                    'unit': {
                        'type': 'string',
                        'enum': ['celsius', 'fahrenheit'],
                        'description': 'Temperature unit',
                    },
                },
                'required': ['location'],
            },
        )
    )


def create_calculate_tool():
    """Create a calculate tool for testing."""
    return ConversationTools(
        function=ConversationToolsFunction(
            name='calculate',
            description='Perform mathematical calculations',
            parameters={
                'type': 'object',
                'properties': {
                    'expression': {
                        'type': 'string',
                        'description': 'Mathematical expression to evaluate',
                    }
                },
                'required': ['expression'],
            },
        )
    )


def create_user_message(text):
    """Helper to create a user message for Alpha2."""
    return ConversationMessage(
        of_user=ConversationMessageOfUser(content=[ConversationMessageContent(text=text)])
    )


def create_system_message(text):
    """Helper to create a system message for Alpha2."""
    return ConversationMessage(
        of_system=ConversationMessageOfSystem(content=[ConversationMessageContent(text=text)])
    )


def create_assistant_message(text, tool_calls=None):
    """Helper to create an assistant message for Alpha2."""
    return ConversationMessage(
        of_assistant=ConversationMessageOfAssistant(
            content=[ConversationMessageContent(text=text)], tool_calls=tool_calls or []
        )
    )


def create_tool_message(tool_id, name, content):
    """Helper to create a tool message for Alpha2."""
    return ConversationMessage(
        of_tool=ConversationMessageOfTool(
            tool_id=tool_id, name=name, content=[ConversationMessageContent(text=content)]
        )
    )


class ConversationTestBase:
    """Base class for conversation tests with common setup."""

    grpc_port = 50011
    http_port = 3510
    scheme = ''

    @classmethod
    def setUpClass(cls):
        cls._fake_dapr_server = FakeDaprSidecar(grpc_port=cls.grpc_port, http_port=cls.http_port)
        cls._fake_dapr_server.start()
        # Configure health check to use fake server's HTTP port
        settings.DAPR_HTTP_PORT = cls.http_port
        settings.DAPR_HTTP_ENDPOINT = f'http://127.0.0.1:{cls.http_port}'

    @classmethod
    def tearDownClass(cls):
        cls._fake_dapr_server.stop()


class ConversationAlpha1SyncTests(ConversationTestBase, unittest.TestCase):
    """Synchronous Alpha1 conversation API tests."""

    def test_basic_conversation_alpha1(self):
        """Test basic Alpha1 conversation functionality."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            inputs = [
                ConversationInput(content='Hello', role='user'),
                ConversationInput(content='How are you?', role='user'),
            ]

            response = client.converse_alpha1(name='test-llm', inputs=inputs)

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 2)
            self.assertIn('Hello', response.outputs[0].result)
            self.assertIn('How are you?', response.outputs[1].result)

    def test_conversation_alpha1_with_options(self):
        """Test Alpha1 conversation with various options."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            inputs = [ConversationInput(content='Hello with options', role='user', scrub_pii=True)]

            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                context_id='test-context-123',
                temperature=0.7,
                scrub_pii=True,
                metadata={'test_key': 'test_value'},
            )

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)
            self.assertEqual(response.context_id, 'test-context-123')

    def test_alpha1_parameter_conversion(self):
        """Test Alpha1 parameter conversion with raw Python values."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            inputs = [ConversationInput(content='Test with parameters', role='user')]

            # Test with raw Python parameters - these should be automatically converted
            response = client.converse_alpha1(
                name='test-llm',
                inputs=inputs,
                parameters={
                    'temperature': 0.7,
                    'max_tokens': 1000,
                    'top_p': 0.9,
                    'frequency_penalty': 0.0,
                    'presence_penalty': 0.0,
                },
            )

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)

    def test_alpha1_error_handling(self):
        """Test Alpha1 conversation error handling."""
        # Setup server to raise an exception
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Alpha1 test error')
        )

        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            inputs = [ConversationInput(content='Error test', role='user')]

            with self.assertRaises(DaprGrpcError) as context:
                client.converse_alpha1(name='test-llm', inputs=inputs)
            self.assertIn('Alpha1 test error', str(context.exception))


class ConversationAlpha2SyncTests(ConversationTestBase, unittest.TestCase):
    """Synchronous Alpha2 conversation API tests."""

    def test_basic_conversation_alpha2(self):
        """Test basic Alpha2 conversation functionality."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Hello Alpha2!')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 1)
            self.assertEqual(len(response.outputs[0].choices), 1)

            choice = response.outputs[0].choices[0]
            self.assertEqual(choice.finish_reason, 'stop')
            self.assertIn('Hello Alpha2!', choice.message.content)

    def test_conversation_alpha2_with_system_message(self):
        """Test Alpha2 conversation with system message."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            system_message = create_system_message('You are a helpful assistant.')
            user_message = create_user_message('Hello!')

            input_alpha2 = ConversationInputAlpha2(
                messages=[system_message, user_message], scrub_pii=False
            )

            response = client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs[0].choices), 2)

            # Check system message response
            system_choice = response.outputs[0].choices[0]
            self.assertIn('System acknowledged', system_choice.message.content)

            # Check user message response
            user_choice = response.outputs[0].choices[1]
            self.assertIn('Response to user', user_choice.message.content)

    def test_conversation_alpha2_with_options(self):
        """Test Alpha2 conversation with various options."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Alpha2 with options')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message], scrub_pii=True)

            response = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                context_id='alpha2-context-123',
                temperature=0.8,
                scrub_pii=True,
                metadata={'alpha2_test': 'true'},
                tool_choice='none',
            )

            self.assertIsNotNone(response)
            self.assertEqual(response.context_id, 'alpha2-context-123')

    def test_alpha2_parameter_conversion(self):
        """Test Alpha2 parameter conversion with various types."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Parameter conversion test')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                parameters={
                    'model': 'gpt-4o-mini',
                    'temperature': 0.7,
                    'max_tokens': 1000,
                    'top_p': 1.0,
                    'frequency_penalty': 0.0,
                    'presence_penalty': 0.0,
                    'stream': False,
                },
            )

            self.assertIsNotNone(response)

    def test_alpha2_error_handling(self):
        """Test Alpha2 conversation error handling."""
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Alpha2 test error')
        )

        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Error test')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            with self.assertRaises(DaprGrpcError) as context:
                client.converse_alpha2(name='test-llm', inputs=[input_alpha2])
            self.assertIn('Alpha2 test error', str(context.exception))


class ConversationToolCallingSyncTests(ConversationTestBase, unittest.TestCase):
    """Synchronous tool calling tests for Alpha2."""

    def test_tool_calling_weather(self):
        """Test tool calling with weather tool."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            weather_tool = create_weather_tool()
            user_message = create_user_message('What is the weather in San Francisco?')

            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm', inputs=[input_alpha2], tools=[weather_tool], tool_choice='auto'
            )

            self.assertIsNotNone(response)
            choice = response.outputs[0].choices[0]
            self.assertEqual(choice.finish_reason, 'tool_calls')
            self.assertEqual(len(choice.message.tool_calls), 1)

            tool_call = choice.message.tool_calls[0]
            self.assertEqual(tool_call.function.name, 'get_weather')
            self.assertIn('San Francisco', tool_call.function.arguments)

    def test_tool_calling_calculate(self):
        """Test tool calling with calculate tool."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            calc_tool = create_calculate_tool()
            user_message = create_user_message('Calculate 15 * 23')

            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm', inputs=[input_alpha2], tools=[calc_tool]
            )

            # Note: Our fake server only triggers weather tools, so this won't return tool calls
            # but it tests that the API works with different tools
            self.assertIsNotNone(response)
            choice = response.outputs[0].choices[0]
            self.assertIn('Calculate', choice.message.content)

    def test_multiple_tools(self):
        """Test conversation with multiple tools."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            weather_tool = create_weather_tool()
            calc_tool = create_calculate_tool()

            user_message = create_user_message('I need weather and calculation help')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                tools=[weather_tool, calc_tool],
                tool_choice='auto',
            )

            self.assertIsNotNone(response)
            # The fake server will call weather tool if "weather" is in the message
            choice = response.outputs[0].choices[0]
            self.assertEqual(choice.finish_reason, 'tool_calls')

    def test_tool_choice_none(self):
        """Test tool choice set to 'none'."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            weather_tool = create_weather_tool()
            user_message = create_user_message('What is the weather today?')

            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm', inputs=[input_alpha2], tools=[weather_tool], tool_choice='none'
            )

            self.assertIsNotNone(response)
            choice = response.outputs[0].choices[0]
            # With tool_choice='none', should not make tool calls even if weather is mentioned
            # (though our fake server may still trigger based on content)
            self.assertIsNotNone(choice.message.content)

    def test_tool_choice_specific(self):
        """Test tool choice set to specific tool name."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            weather_tool = create_weather_tool()
            calc_tool = create_calculate_tool()

            user_message = create_user_message('What is the weather like?')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                tools=[weather_tool, calc_tool],
                tool_choice='get_weather',
            )

            self.assertIsNotNone(response)
            choice = response.outputs[0].choices[0]
            if choice.finish_reason == 'tool_calls':
                tool_call = choice.message.tool_calls[0]
                self.assertEqual(tool_call.function.name, 'get_weather')


class ConversationMultiTurnSyncTests(ConversationTestBase, unittest.TestCase):
    """Multi-turn conversation tests for Alpha2."""

    def test_multi_turn_conversation(self):
        """Test multi-turn conversation with different message types."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            # Create a conversation with system, user, and assistant messages
            system_message = create_system_message('You are a helpful AI assistant.')
            user_message1 = create_user_message('Hello, how are you?')
            assistant_message = create_assistant_message('I am doing well, thank you!')
            user_message2 = create_user_message('What can you help me with?')

            input_alpha2 = ConversationInputAlpha2(
                messages=[system_message, user_message1, assistant_message, user_message2]
            )

            response = client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs[0].choices), 4)

            # Check each response type
            choices = response.outputs[0].choices
            self.assertIn('System acknowledged', choices[0].message.content)
            self.assertIn('Response to user', choices[1].message.content)
            self.assertIn('Assistant continued', choices[2].message.content)
            self.assertIn('Response to user', choices[3].message.content)

    def test_tool_calling_workflow(self):
        """Test complete tool calling workflow."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            # Step 1: User asks for weather
            weather_tool = create_weather_tool()
            user_message = create_user_message('What is the weather in Tokyo?')

            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response1 = client.converse_alpha2(
                name='test-llm', inputs=[input_alpha2], tools=[weather_tool]
            )

            # Should get tool call
            self.assertIsNotNone(response1)
            choice = response1.outputs[0].choices[0]
            self.assertEqual(choice.finish_reason, 'tool_calls')
            tool_call = choice.message.tool_calls[0]

            # Step 2: Send tool result back
            tool_result_message = create_tool_message(
                tool_id=tool_call.id,
                name='get_weather',
                content='{"temperature": 18, "condition": "cloudy", "humidity": 75}',
            )

            result_input = ConversationInputAlpha2(messages=[tool_result_message])

            response2 = client.converse_alpha2(name='test-llm', inputs=[result_input])

            # Should get processed tool result
            self.assertIsNotNone(response2)
            result_choice = response2.outputs[0].choices[0]
            self.assertIn('Tool result processed', result_choice.message.content)

    def test_conversation_context_continuity(self):
        """Test conversation context continuity with context_id."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            context_id = 'multi-turn-test-123'

            # First turn
            user_message1 = create_user_message('My name is Alice.')
            input1 = ConversationInputAlpha2(messages=[user_message1])

            response1 = client.converse_alpha2(
                name='test-llm', inputs=[input1], context_id=context_id
            )

            self.assertEqual(response1.context_id, context_id)

            # Second turn with same context
            user_message2 = create_user_message('What is my name?')
            input2 = ConversationInputAlpha2(messages=[user_message2])

            response2 = client.converse_alpha2(
                name='test-llm', inputs=[input2], context_id=context_id
            )

            self.assertEqual(response2.context_id, context_id)
            self.assertIsNotNone(response2.outputs[0].choices[0].message.content)


class ConversationAsyncTests(ConversationTestBase, unittest.IsolatedAsyncioTestCase):
    """Asynchronous conversation API tests."""

    async def test_basic_async_conversation_alpha1(self):
        """Test basic async Alpha1 conversation."""
        async with AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            inputs = [
                ConversationInput(content='Hello async', role='user'),
                ConversationInput(content='How are you async?', role='user'),
            ]

            response = await client.converse_alpha1(name='test-llm', inputs=inputs)

            self.assertIsNotNone(response)
            self.assertEqual(len(response.outputs), 2)
            self.assertIn('Hello async', response.outputs[0].result)

    async def test_basic_async_conversation_alpha2(self):
        """Test basic async Alpha2 conversation."""
        async with AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Hello async Alpha2!')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = await client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

            self.assertIsNotNone(response)
            choice = response.outputs[0].choices[0]
            self.assertIn('Hello async Alpha2!', choice.message.content)

    async def test_async_tool_calling(self):
        """Test async tool calling."""
        async with AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            weather_tool = create_weather_tool()
            user_message = create_user_message('Async weather request for London')

            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = await client.converse_alpha2(
                name='test-llm', inputs=[input_alpha2], tools=[weather_tool]
            )

            self.assertIsNotNone(response)
            choice = response.outputs[0].choices[0]
            self.assertEqual(choice.finish_reason, 'tool_calls')
            tool_call = choice.message.tool_calls[0]
            self.assertEqual(tool_call.function.name, 'get_weather')

    async def test_concurrent_async_conversations(self):
        """Test multiple concurrent async conversations."""
        async with AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:

            async def run_alpha1_conversation(message, session_id):
                inputs = [ConversationInput(content=message, role='user')]
                response = await client.converse_alpha1(
                    name='test-llm', inputs=inputs, context_id=session_id
                )
                return response.outputs[0].result

            async def run_alpha2_conversation(message, session_id):
                user_message = create_user_message(message)
                input_alpha2 = ConversationInputAlpha2(messages=[user_message])
                response = await client.converse_alpha2(
                    name='test-llm', inputs=[input_alpha2], context_id=session_id
                )
                return response.outputs[0].choices[0].message.content

            # Run concurrent conversations with both Alpha1 and Alpha2
            tasks = [
                run_alpha1_conversation('First Alpha1 message', 'concurrent-alpha1'),
                run_alpha2_conversation('First Alpha2 message', 'concurrent-alpha2'),
                run_alpha1_conversation('Second Alpha1 message', 'concurrent-alpha1-2'),
                run_alpha2_conversation('Second Alpha2 message', 'concurrent-alpha2-2'),
            ]

            results = await asyncio.gather(*tasks)

            self.assertEqual(len(results), 4)
            for result in results:
                self.assertIsNotNone(result)
                self.assertIsInstance(result, str)

    async def test_async_multi_turn_with_tools(self):
        """Test async multi-turn conversation with tool calling."""
        async with AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            # First turn: user asks for weather
            weather_tool = create_weather_tool()
            user_message = create_user_message('Async weather for Paris')
            input1 = ConversationInputAlpha2(messages=[user_message])

            response1 = await client.converse_alpha2(
                name='test-llm',
                inputs=[input1],
                tools=[weather_tool],
                context_id='async-multi-turn',
            )

            # Should get tool call
            self.assertEqual(response1.outputs[0].choices[0].finish_reason, 'tool_calls')
            tool_call = response1.outputs[0].choices[0].message.tool_calls[0]

            # Second turn: provide tool result
            tool_result_message = create_tool_message(
                tool_id=tool_call.id,
                name='get_weather',
                content='{"temperature": 22, "condition": "sunny"}',
            )
            input2 = ConversationInputAlpha2(messages=[tool_result_message])

            response2 = await client.converse_alpha2(
                name='test-llm', inputs=[input2], context_id='async-multi-turn'
            )

            self.assertIsNotNone(response2)
            self.assertIn('Tool result processed', response2.outputs[0].choices[0].message.content)

    async def test_async_error_handling(self):
        """Test async conversation error handling."""
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Async test error')
        )

        async with AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            inputs = [ConversationInput(content='Async error test', role='user')]

            with self.assertRaises(DaprGrpcError) as context:
                await client.converse_alpha1(name='test-llm', inputs=inputs)
            self.assertIn('Async test error', str(context.exception))


class ConversationParameterTests(ConversationTestBase, unittest.TestCase):
    """Tests for parameter handling and conversion."""

    def test_parameter_edge_cases(self):
        """Test parameter conversion with edge cases."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Edge cases test')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            response = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                parameters={
                    'int32_max': 2147483647,  # Int32 maximum
                    'int64_large': 9999999999,  # Requires Int64
                    'negative_temp': -0.5,  # Negative float
                    'zero_value': 0,  # Zero integer
                    'false_flag': False,  # Boolean false
                    'true_flag': True,  # Boolean true
                    'empty_string': '',  # Empty string
                },
            )

            self.assertIsNotNone(response)

    def test_realistic_provider_parameters(self):
        """Test with realistic LLM provider parameters."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            user_message = create_user_message('Provider parameters test')
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])

            # OpenAI-style parameters
            response1 = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                parameters={
                    'model': 'gpt-4o-mini',
                    'temperature': 0.7,
                    'max_tokens': 1000,
                    'top_p': 1.0,
                    'frequency_penalty': 0.0,
                    'presence_penalty': 0.0,
                    'stream': False,
                    'tool_choice': 'auto',
                },
            )

            # Anthropic-style parameters
            response2 = client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                parameters={
                    'model': 'claude-3-5-sonnet-20241022',
                    'max_tokens': 4096,
                    'temperature': 0.8,
                    'top_p': 0.9,
                    'top_k': 250,
                    'stream': False,
                },
            )

            self.assertIsNotNone(response1)
            self.assertIsNotNone(response2)


class ConversationValidationTests(ConversationTestBase, unittest.TestCase):
    """Tests for input validation and edge cases."""

    def test_empty_inputs_alpha1(self):
        """Test Alpha1 with empty inputs."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            response = client.converse_alpha1(name='test-llm', inputs=[])
            self.assertIsNotNone(response)

    def test_empty_inputs_alpha2(self):
        """Test Alpha2 with empty inputs."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            response = client.converse_alpha2(name='test-llm', inputs=[])
            self.assertIsNotNone(response)

    def test_empty_messages_alpha2(self):
        """Test Alpha2 with empty messages in input."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            input_alpha2 = ConversationInputAlpha2(messages=[])
            response = client.converse_alpha2(name='test-llm', inputs=[input_alpha2])
            self.assertIsNotNone(response)

    def test_mixed_alpha1_alpha2_compatibility(self):
        """Test that Alpha1 and Alpha2 can be used in the same session."""
        with DaprClient(f'{self.scheme}localhost:{self.grpc_port}') as client:
            # Alpha1 call
            alpha1_inputs = [ConversationInput(content='Alpha1 call', role='user')]
            alpha1_response = client.converse_alpha1(name='test-llm', inputs=alpha1_inputs)

            # Alpha2 call
            user_message = create_user_message('Alpha2 call')
            alpha2_input = ConversationInputAlpha2(messages=[user_message])
            alpha2_response = client.converse_alpha2(name='test-llm', inputs=[alpha2_input])

            # Both should work
            self.assertIsNotNone(alpha1_response)
            self.assertIsNotNone(alpha2_response)

            # Check response structures are different but valid
            self.assertTrue(hasattr(alpha1_response, 'outputs'))
            self.assertTrue(hasattr(alpha2_response, 'outputs'))
            self.assertTrue(hasattr(alpha2_response.outputs[0], 'choices'))


class ConversationToolHelpersSyncTests(unittest.TestCase):
    """Tests for conversation tool helpers, registry, and backends (sync)."""

    def tearDown(self):
        # Cleanup tools with known prefixes
        for t in list(get_registered_tools()):
            try:
                name = t.function.name
                if name.startswith('test_') or name.startswith('ns_') or name.startswith('dup_'):
                    unregister_tool(name)
            except Exception:
                continue

    def test_tool_decorator_namespace_and_name_override(self):
        ns_unique = uuid.uuid4().hex[:6]
        name_override = f'test_sum_{ns_unique}'

        @tool_decorator(namespace=f'ns.{ns_unique}', name=name_override)
        def foo(x: int, y: int) -> int:
            return x + y

        names = {t.function.name for t in get_registered_tools()}
        self.assertIn(name_override, names)
        unregister_tool(name_override)

        ns_tool = f'ns.{ns_unique}.bar'

        @tool_decorator(namespace=f'ns.{ns_unique}')
        def bar(q: int) -> int:
            return q * 2

        names = {t.function.name for t in get_registered_tools()}
        self.assertIn(ns_tool, names)
        unregister_tool(ns_tool)

    def test_register_tool_duplicate_raises(self):
        dup_name = f'dup_tool_{uuid.uuid4().hex[:6]}'
        ct = ConversationTools(
            function=ConversationToolsFunction(name=dup_name, parameters={'type': 'object'}),
            backend=FunctionBackend(lambda: None),
        )
        register_tool(dup_name, ct)
        try:
            with self.assertRaises(ValueError):
                register_tool(dup_name, ct)
        finally:
            unregister_tool(dup_name)

    def test_conversationtools_invoke_without_backend_raises(self):
        ct = ConversationTools(
            function=ConversationToolsFunction(
                name='test_no_backend', parameters={'type': 'object'}
            ),
            backend=None,
        )
        with self.assertRaises(ToolExecutionError):
            ct.invoke({'a': 1})

        async def run():
            with self.assertRaises(ToolExecutionError):
                await ct.ainvoke({'a': 1})

        asyncio.run(run())

    def test_functionbackend_sync_and_async_and_timeout(self):
        def mul(a: int, b: int) -> int:
            return a * b

        fb_sync = FunctionBackend(mul)
        self.assertEqual(
            fb_sync.invoke(ConversationToolsFunction(name='mul'), {'a': 3, 'b': 5}),
            15,
        )

        async def run_sync_via_async():
            res = await fb_sync.ainvoke(ConversationToolsFunction(name='mul'), {'a': 2, 'b': 7})
            self.assertEqual(res, 14)

        asyncio.run(run_sync_via_async())

        async def wait_and_return(x: int, delay: float = 0.01) -> int:
            await asyncio.sleep(delay)
            return x

        fb_async = FunctionBackend(wait_and_return)
        with self.assertRaises(ToolExecutionError):
            fb_async.invoke(ConversationToolsFunction(name='wait'), {'x': 1})

        async def run_async_ok():
            res = await fb_async.ainvoke(ConversationToolsFunction(name='wait'), {'x': 42})
            self.assertEqual(res, 42)

        asyncio.run(run_async_ok())

        async def run_async_timeout():
            with self.assertRaises(ToolExecutionError):
                await fb_async.ainvoke(
                    ConversationToolsFunction(name='wait'),
                    {'x': 1, 'delay': 0.2},
                    timeout=0.01,
                )

        asyncio.run(run_async_timeout())

        with self.assertRaises(ToolArgumentError):
            fb_sync.invoke(ConversationToolsFunction(name='mul'), {'a': 1})

        async def run_missing_arg_async():
            with self.assertRaises(ToolArgumentError):
                await fb_sync.ainvoke(ConversationToolsFunction(name='mul'), {'a': 1})

        asyncio.run(run_missing_arg_async())

    def test_conversationtoolsfunction_from_function_and_schema(self):
        def greet(name: str, punctuation: str = '!') -> str:
            """Say hello.

            Args:
                name: Person to greet
                punctuation: Trailing punctuation
            """

            return f'Hello, {name}{punctuation}'

        spec = ConversationToolsFunction.from_function(greet, register=False)
        schema = spec.schema_as_dict()
        self.assertIn('name', schema.get('properties', {}))
        self.assertIn('name', schema.get('required', []))
        self.assertIn('punctuation', schema.get('properties', {}))

        spec2 = ConversationToolsFunction.from_function(greet, register=True)
        try:
            names = {t.function.name for t in get_registered_tools()}
            self.assertIn(spec2.name, names)
        finally:
            unregister_tool(spec2.name)

    def test_message_helpers_and_to_proto(self):
        user_msg = conversation.create_user_message('hi')
        self.assertIsNotNone(user_msg.of_user)
        self.assertEqual(user_msg.of_user.content[0].text, 'hi')
        proto_user = user_msg.to_proto()
        self.assertEqual(proto_user.of_user.content[0].text, 'hi')

        sys_msg = conversation.create_system_message('sys')
        proto_sys = sys_msg.to_proto()
        self.assertEqual(proto_sys.of_system.content[0].text, 'sys')

        tc = conversation.ConversationToolCalls(
            id='abc123',
            function=conversation.ConversationToolCallsOfFunction(name='fn', arguments='{}'),
        )
        asst_msg = conversation.ConversationMessage(
            of_assistant=conversation.ConversationMessageOfAssistant(
                content=[conversation.ConversationMessageContent(text='ok')],
                tool_calls=[tc],
            )
        )
        proto_asst = asst_msg.to_proto()
        self.assertEqual(proto_asst.of_assistant.content[0].text, 'ok')
        self.assertEqual(proto_asst.of_assistant.tool_calls[0].function.name, 'fn')

        tool_msg = conversation.create_tool_message('tid1', 'get_weather', 'cloudy')
        proto_tool = tool_msg.to_proto()
        self.assertEqual(proto_tool.of_tool.tool_id, 'tid1')
        self.assertEqual(proto_tool.of_tool.name, 'get_weather')
        self.assertEqual(proto_tool.of_tool.content[0].text, 'cloudy')


class ConversationToolHelpersAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        for t in list(get_registered_tools()):
            try:
                name = t.function.name
                if name.startswith('test_'):
                    unregister_tool(name)
            except Exception:
                continue

    async def test_execute_registered_tool_async(self):
        unique = uuid.uuid4().hex[:8]
        tool_name = f'test_async_{unique}'

        @tool_decorator(name=tool_name)
        async def echo(value: str, delay: float = 0.0) -> str:
            await asyncio.sleep(delay)
            return value

        out = await execute_registered_tool_async(tool_name, {'value': 'hello'})
        self.assertEqual(out, 'hello')

        with self.assertRaises(ToolExecutionError):
            await execute_registered_tool_async(
                tool_name, {'value': 'slow', 'delay': 0.2}, timeout=0.01
            )
        unregister_tool(tool_name)


if __name__ == '__main__':
    unittest.main()
