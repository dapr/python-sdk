# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import asyncio
import json
import unittest
import uuid
from unittest.mock import Mock, patch

from google.protobuf.struct_pb2 import Struct
from google.rpc import code_pb2, status_pb2

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprGrpcError
from dapr.clients.grpc import conversation
from dapr.clients.grpc._conversation_helpers import (
    ToolArgumentError,
    ToolExecutionError,
    ToolNotFoundError,
)
from dapr.clients.grpc.conversation import (
    ConversationInput,
    ConversationInputAlpha2,
    ConversationMessage,
    ConversationMessageOfAssistant,
    ConversationResponseAlpha2,
    ConversationResultAlpha2,
    ConversationResultAlpha2Choices,
    ConversationResultAlpha2CompletionUsage,
    ConversationResultAlpha2CompletionUsageCompletionTokensDetails,
    ConversationResultAlpha2CompletionUsagePromptTokensDetails,
    ConversationResultAlpha2Message,
    ConversationToolCalls,
    ConversationToolCallsOfFunction,
    ConversationTools,
    ConversationToolsFunction,
    FunctionBackend,
    _get_outputs_from_grpc_response,
    create_assistant_message,
    create_system_message,
    create_tool_message,
    create_user_message,
    execute_registered_tool,
    execute_registered_tool_async,
    get_registered_tools,
    register_tool,
    unregister_tool,
)
from dapr.clients.grpc.conversation import (
    tool as tool_decorator,
)
from dapr.conf import settings
from tests.clients.fake_dapr_server import FakeDaprSidecar

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


class ConversationTestBaseSync(ConversationTestBase, unittest.TestCase):
    """Base class for conversation tests with common setup."""

    def setUp(self):
        super().setUp()
        self.client = DaprClient(f'{self.scheme}localhost:{self.grpc_port}')

    def tearDown(self):
        super().tearDown()
        self.client.close()


class ConversationTestBaseAsync(ConversationTestBase, unittest.IsolatedAsyncioTestCase):
    """Base class for conversation tests with common setup."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.client = AsyncDaprClient(f'{self.scheme}localhost:{self.grpc_port}')

    async def asyncTearDown(self):
        await super().asyncTearDown()
        await self.client.close()


class ConversationAlpha1SyncTests(ConversationTestBaseSync):
    """Synchronous Alpha1 conversation API tests."""

    def test_basic_conversation_alpha1(self):
        """Test basic Alpha1 conversation functionality."""
        inputs = [
            ConversationInput(content='Hello', role='user'),
            ConversationInput(content='How are you?', role='user'),
        ]

        response = self.client.converse_alpha1(name='test-llm', inputs=inputs)

        self.assertIsNotNone(response)
        self.assertEqual(len(response.outputs), 2)
        self.assertIn('Hello', response.outputs[0].result)
        self.assertIn('How are you?', response.outputs[1].result)

    def test_conversation_alpha1_with_options(self):
        """Test Alpha1 conversation with various options."""
        inputs = [ConversationInput(content='Hello with options', role='user', scrub_pii=True)]

        response = self.client.converse_alpha1(
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
        inputs = [ConversationInput(content='Test with parameters', role='user')]

        # Test with raw Python parameters - these should be automatically converted
        response = self.client.converse_alpha1(
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

        inputs = [ConversationInput(content='Error test', role='user')]

        with self.assertRaises(DaprGrpcError) as context:
            self.client.converse_alpha1(name='test-llm', inputs=inputs)
            self.assertIn('Alpha1 test error', str(context.exception))


class ConversationAlpha2SyncTests(ConversationTestBaseSync):
    """Synchronous Alpha2 conversation API tests."""

    def test_basic_conversation_alpha2(self):
        """Test basic Alpha2 conversation functionality."""
        user_message = create_user_message('Hello Alpha2!')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

        self.assertIsNotNone(response)
        self.assertEqual(len(response.outputs), 1)
        self.assertEqual(len(response.outputs[0].choices), 1)

        choice = response.outputs[0].choices[0]
        self.assertEqual(choice.finish_reason, 'stop')
        self.assertIn('Hello Alpha2!', choice.message.content)

        out = response.outputs[0]
        if out.model is not None:
            self.assertEqual(out.model, 'test-llm')
        if out.usage is not None:
            self.assertGreaterEqual(out.usage.total_tokens, 15)
            self.assertGreaterEqual(out.usage.prompt_tokens, 5)
            self.assertGreaterEqual(out.usage.completion_tokens, 10)

    def test_conversation_alpha2_with_system_message(self):
        """Test Alpha2 conversation with system message."""
        system_message = create_system_message('You are a helpful assistant.')
        user_message = create_user_message('Hello!')

        input_alpha2 = ConversationInputAlpha2(
            messages=[system_message, user_message], scrub_pii=False
        )

        response = self.client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

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
        user_message = create_user_message('Alpha2 with options')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message], scrub_pii=True)

        response = self.client.converse_alpha2(
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
        user_message = create_user_message('Parameter conversion test')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
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

        user_message = create_user_message('Error test')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        with self.assertRaises(DaprGrpcError) as context:
            self.client.converse_alpha2(name='test-llm', inputs=[input_alpha2])
        self.assertIn('Alpha2 test error', str(context.exception))


class ConversationToolCallingSyncTests(ConversationTestBaseSync):
    """Synchronous tool calling tests for Alpha2."""

    def test_tool_calling_weather(self):
        """Test tool calling with weather tool."""
        weather_tool = create_weather_tool()
        user_message = create_user_message('What is the weather in San Francisco?')

        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
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
        calc_tool = create_calculate_tool()
        user_message = create_user_message('Calculate 15 * 23')

        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
            name='test-llm', inputs=[input_alpha2], tools=[calc_tool]
        )

        # Note: Our fake server only triggers weather tools, so this won't return tool calls
        # but it tests that the API works with different tools
        self.assertIsNotNone(response)
        choice = response.outputs[0].choices[0]
        self.assertIn('Calculate', choice.message.content)

    def test_multiple_tools(self):
        """Test conversation with multiple tools."""
        weather_tool = create_weather_tool()
        calc_tool = create_calculate_tool()

        user_message = create_user_message('I need weather and calculation help')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
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

        weather_tool = create_weather_tool()
        user_message = create_user_message('What is the weather today?')

        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
            name='test-llm', inputs=[input_alpha2], tools=[weather_tool], tool_choice='none'
        )

        self.assertIsNotNone(response)
        choice = response.outputs[0].choices[0]
        # With tool_choice='none', should not make tool calls even if weather is mentioned
        # (though our fake server may still trigger based on content)
        self.assertIsNotNone(choice.message.content)

    def test_tool_choice_specific(self):
        """Test tool choice set to specific tool name."""
        weather_tool = create_weather_tool()
        calc_tool = create_calculate_tool()

        user_message = create_user_message('What is the weather like?')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
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


class ConversationMultiTurnSyncTests(ConversationTestBaseSync):
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


class ConversationAsyncTests(ConversationTestBaseAsync):
    """Asynchronous conversation API tests."""

    async def test_basic_async_conversation_alpha1(self):
        """Test basic async Alpha1 conversation."""
        inputs = [
            ConversationInput(content='Hello async', role='user'),
            ConversationInput(content='How are you async?', role='user'),
        ]

        response = await self.client.converse_alpha1(name='test-llm', inputs=inputs)

        self.assertIsNotNone(response)
        self.assertEqual(len(response.outputs), 2)
        self.assertIn('Hello async', response.outputs[0].result)

    async def test_basic_async_conversation_alpha2(self):
        """Test basic async Alpha2 conversation."""
        user_message = create_user_message('Hello async Alpha2!')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = await self.client.converse_alpha2(name='test-llm', inputs=[input_alpha2])

        self.assertIsNotNone(response)
        choice = response.outputs[0].choices[0]
        self.assertIn('Hello async Alpha2!', choice.message.content)

    async def test_async_tool_calling(self):
        """Test async tool calling."""
        weather_tool = create_weather_tool()
        user_message = create_user_message('Async weather request for London')

        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = await self.client.converse_alpha2(
            name='test-llm', inputs=[input_alpha2], tools=[weather_tool]
        )

        self.assertIsNotNone(response)
        choice = response.outputs[0].choices[0]
        self.assertEqual(choice.finish_reason, 'tool_calls')
        tool_call = choice.message.tool_calls[0]
        self.assertEqual(tool_call.function.name, 'get_weather')

    async def test_concurrent_async_conversations(self):
        """Test multiple concurrent async conversations."""

        async def run_alpha1_conversation(message, session_id):
            inputs = [ConversationInput(content=message, role='user')]
            response = await self.client.converse_alpha1(
                name='test-llm', inputs=inputs, context_id=session_id
            )
            return response.outputs[0].result

        async def run_alpha2_conversation(message, session_id):
            user_message = create_user_message(message)
            input_alpha2 = ConversationInputAlpha2(messages=[user_message])
            response = await self.client.converse_alpha2(
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
        # First turn: user asks for weather
        weather_tool = create_weather_tool()
        user_message = create_user_message('Async weather for Paris')
        input1 = ConversationInputAlpha2(messages=[user_message])

        response1 = await self.client.converse_alpha2(
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

        response2 = await self.client.converse_alpha2(
            name='test-llm', inputs=[input2], context_id='async-multi-turn'
        )

        self.assertIsNotNone(response2)
        self.assertIn('Tool result processed', response2.outputs[0].choices[0].message.content)

    async def test_async_error_handling(self):
        """Test async conversation error handling."""
        self._fake_dapr_server.raise_exception_on_next_call(
            status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message='Async test error')
        )

        inputs = [ConversationInput(content='Async error test', role='user')]

        with self.assertRaises(DaprGrpcError) as context:
            await self.client.converse_alpha1(name='test-llm', inputs=inputs)
        self.assertIn('Async test error', str(context.exception))


class ConversationParameterTests(ConversationTestBaseSync):
    """Tests for parameter handling and conversion."""

    def test_parameter_edge_cases(self):
        """Test parameter conversion with edge cases."""
        user_message = create_user_message('Edge cases test')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        response = self.client.converse_alpha2(
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
        user_message = create_user_message('Provider parameters test')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])

        # OpenAI-style parameters
        response1 = self.client.converse_alpha2(
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
        response2 = self.client.converse_alpha2(
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


class ConversationValidationTests(ConversationTestBaseSync):
    """Tests for input validation and edge cases."""

    def test_empty_inputs_alpha1(self):
        """Test Alpha1 with empty inputs."""
        response = self.client.converse_alpha1(name='test-llm', inputs=[])
        self.assertIsNotNone(response)

    def test_empty_inputs_alpha2(self):
        """Test Alpha2 with empty inputs."""
        response = self.client.converse_alpha2(name='test-llm', inputs=[])
        self.assertIsNotNone(response)

    def test_empty_messages_alpha2(self):
        """Test Alpha2 with empty messages in input."""
        input_alpha2 = ConversationInputAlpha2(messages=[])
        response = self.client.converse_alpha2(name='test-llm', inputs=[input_alpha2])
        self.assertIsNotNone(response)

    def test_mixed_alpha1_alpha2_compatibility(self):
        """Test that Alpha1 and Alpha2 can be used in the same session."""
        # Alpha1 call
        alpha1_inputs = [ConversationInput(content='Alpha1 call', role='user')]
        alpha1_response = self.client.converse_alpha1(name='test-llm', inputs=alpha1_inputs)

        # Alpha2 call
        user_message = create_user_message('Alpha2 call')
        alpha2_input = ConversationInputAlpha2(messages=[user_message])
        alpha2_response = self.client.converse_alpha2(name='test-llm', inputs=[alpha2_input])

        # Both should work
        self.assertIsNotNone(alpha1_response)
        self.assertIsNotNone(alpha2_response)

        # Check response structures are different but valid
        self.assertTrue(hasattr(alpha1_response, 'outputs'))
        self.assertTrue(hasattr(alpha2_response, 'outputs'))
        self.assertTrue(hasattr(alpha2_response.outputs[0], 'choices'))


class ConversationToolHelpersSyncTests(ConversationTestBaseSync):
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


class ConversationToolHelpersAsyncTests(ConversationTestBaseAsync):
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


class TestStringifyToolOutputIntegration(unittest.TestCase):
    def test_create_tool_message_with_bytes_and_bytearray(self):
        import base64

        # bytes
        raw = bytes([0, 1, 2, 250, 255])
        msg = create_tool_message('tidb', 'bin', raw)
        self.assertTrue(msg.of_tool.content[0].text.startswith('base64:'))
        self.assertEqual(
            msg.of_tool.content[0].text,
            'base64:' + base64.b64encode(raw).decode('ascii'),
        )
        # bytearray
        ba = bytearray(raw)
        msg2 = create_tool_message('tidb2', 'bin', ba)
        self.assertEqual(
            msg2.of_tool.content[0].text,
            'base64:' + base64.b64encode(bytes(ba)).decode('ascii'),
        )

    def test_create_tool_message_with_dataclass_and_plain_object(self):
        import json
        from dataclasses import dataclass

        @dataclass
        class P:
            x: int
            y: str

        p = P(3, 'z')
        msg = create_tool_message('tiddc', 'dc', p)
        self.assertEqual(json.loads(msg.of_tool.content[0].text), {'x': 3, 'y': 'z'})

        class Plain:
            def __init__(self):
                self.a = 1
                self.b = 'b'
                self.fn = lambda: 42  # filtered out

        obj = Plain()
        msg2 = create_tool_message('tidobj', 'plain', obj)
        self.assertEqual(json.loads(msg2.of_tool.content[0].text), {'a': 1, 'b': 'b'})

    def test_create_tool_message_json_failure_falls_back_to_str(self):
        class Bad:
            def __init__(self):
                self.s = {1, 2, 3}  # set not JSON serializable

            def __str__(self):
                return 'badobj'

        m = create_tool_message('tidbad', 'bad', Bad())
        self.assertEqual(m.of_tool.content[0].text, 'badobj')


class TestIndentLines(unittest.TestCase):
    def test_single_line_with_indent(self):
        result = conversation._indent_lines('Note', 'Hello', 2)
        self.assertEqual(result, '  Note: Hello')

    def test_multiline_example(self):
        text = 'This is a long\nmultiline\ntext block'
        result = conversation._indent_lines('Description', text, 4)
        expected = (
            '    Description: This is a long\n'
            '                 multiline\n'
            '                 text block'
        )
        self.assertEqual(result, expected)

    def test_zero_indent(self):
        result = conversation._indent_lines('Title', 'Line one\nLine two', 0)
        expected = 'Title: Line one\n       Line two'
        self.assertEqual(result, expected)

    def test_empty_string(self):
        result = conversation._indent_lines('Empty', '', 3)
        # Should end with a space after colon
        self.assertEqual(result, '   Empty: ')

    def test_none_text(self):
        result = conversation._indent_lines('NoneCase', None, 1)
        self.assertEqual(result, ' NoneCase: ')

    def test_title_length_affects_indent(self):
        # Title length is 1, indent_after_first_line should be indent + len(title) + 2
        # indent=2, len(title)=1 => 2 + 1 + 2 = 5 spaces on continuation lines
        result = conversation._indent_lines('T', 'a\nb', 2)
        expected = '  T: a\n     b'
        self.assertEqual(result, expected)


class TestToAssistantMessages(unittest.TestCase):
    def test_single_choice_content_only(self):
        # Prepare a response with a single output and single choice, content only
        msg = ConversationResultAlpha2Message(content='Hello from assistant!', tool_calls=[])
        choice = ConversationResultAlpha2Choices(finish_reason='stop', index=0, message=msg)
        response = ConversationResponseAlpha2(
            context_id='ctx1', outputs=[ConversationResultAlpha2(choices=[choice])]
        )

        out = response.to_assistant_messages()

        self.assertIsInstance(out, list)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], ConversationMessage)
        self.assertIsNotNone(out[0].of_assistant)
        self.assertIsInstance(out[0].of_assistant, ConversationMessageOfAssistant)
        self.assertEqual(len(out[0].of_assistant.content), 1)
        self.assertEqual(out[0].of_assistant.content[0].text, 'Hello from assistant!')
        self.assertEqual(len(out[0].of_assistant.tool_calls), 0)

    def test_multiple_outputs_and_choices(self):
        # Prepare response with 2 outputs, each with 2 choices
        def make_choice(idx: int, text: str) -> ConversationResultAlpha2Choices:
            return ConversationResultAlpha2Choices(
                finish_reason='stop',
                index=idx,
                message=ConversationResultAlpha2Message(content=text, tool_calls=[]),
            )

        outputs = [
            ConversationResultAlpha2(choices=[make_choice(0, 'A1'), make_choice(1, 'A2')]),
            ConversationResultAlpha2(choices=[make_choice(0, 'B1'), make_choice(1, 'B2')]),
        ]

        response = ConversationResponseAlpha2(context_id=None, outputs=outputs)
        out = response.to_assistant_messages()

        # Expect 4 assistant messages in order
        self.assertEqual(len(out), 4)
        texts = [m.of_assistant.content[0].text for m in out]
        self.assertEqual(texts, ['A1', 'A2', 'B1', 'B2'])

    def test_choice_with_tool_calls_preserved(self):
        tool_call = ConversationToolCalls(
            id='call-123',
            function=ConversationToolCallsOfFunction(
                name='get_weather', arguments='{"location":"Paris","unit":"celsius"}'
            ),
        )
        msg = ConversationResultAlpha2Message(content='', tool_calls=[tool_call])
        choice = ConversationResultAlpha2Choices(finish_reason='tool_calls', index=0, message=msg)
        response = ConversationResponseAlpha2(
            context_id='ctx2', outputs=[ConversationResultAlpha2(choices=[choice])]
        )

        out = response.to_assistant_messages()

        self.assertEqual(len(out), 1)
        asst = out[0].of_assistant
        self.assertIsNotNone(asst)
        self.assertEqual(len(asst.content), 0)
        self.assertEqual(len(asst.tool_calls), 1)
        tc = asst.tool_calls[0]
        self.assertEqual(tc.id, 'call-123')
        self.assertIsNotNone(tc.function)
        self.assertEqual(tc.function.name, 'get_weather')
        self.assertEqual(tc.function.arguments, '{"location":"Paris","unit":"celsius"}')

    def test_empty_and_none_outputs(self):
        # Empty list outputs
        response_empty = ConversationResponseAlpha2(context_id=None, outputs=[])
        self.assertEqual(response_empty.to_assistant_messages(), [])

        # None outputs (even though type says List, code handles None via `or []`)
        response_none = ConversationResponseAlpha2(context_id=None, outputs=None)  # type: ignore[arg-type]
        self.assertEqual(response_none.to_assistant_messages(), [])


class TestConversationResultAlpha2ModelAndUsage(unittest.TestCase):
    """Tests for model and usage fields on ConversationResultAlpha2 and related types."""

    def test_result_alpha2_has_model_and_usage_attributes(self):
        """ConversationResultAlpha2 accepts and exposes model and usage."""
        msg = ConversationResultAlpha2Message(content='Hi', tool_calls=[])
        choice = ConversationResultAlpha2Choices(finish_reason='stop', index=0, message=msg)
        usage = ConversationResultAlpha2CompletionUsage(
            completion_tokens=10,
            prompt_tokens=5,
            total_tokens=15,
        )
        result = ConversationResultAlpha2(
            choices=[choice],
            model='test-model-1',
            usage=usage,
        )
        self.assertEqual(result.model, 'test-model-1')
        self.assertIsNotNone(result.usage)
        self.assertEqual(result.usage.completion_tokens, 10)
        self.assertEqual(result.usage.prompt_tokens, 5)
        self.assertEqual(result.usage.total_tokens, 15)

    def test_result_alpha2_model_and_usage_default_none(self):
        """ConversationResultAlpha2 optional fields default to None when not provided.

        When the API returns a response, model and usage are set from the conversation
        component. This test only checks that the dataclass defaults are None when
        constructing with choices only.
        """
        msg = ConversationResultAlpha2Message(content='Hi', tool_calls=[])
        choice = ConversationResultAlpha2Choices(finish_reason='stop', index=0, message=msg)
        result = ConversationResultAlpha2(choices=[choice])
        self.assertIsNone(result.model)
        self.assertIsNone(result.usage)

    def test_usage_completion_and_prompt_details(self):
        """ConversationResultAlpha2CompletionUsage supports details."""
        completion_details = ConversationResultAlpha2CompletionUsageCompletionTokensDetails(
            accepted_prediction_tokens=1,
            audio_tokens=2,
            reasoning_tokens=3,
            rejected_prediction_tokens=0,
        )
        prompt_details = ConversationResultAlpha2CompletionUsagePromptTokensDetails(
            audio_tokens=0,
            cached_tokens=4,
        )
        usage = ConversationResultAlpha2CompletionUsage(
            completion_tokens=10,
            prompt_tokens=5,
            total_tokens=15,
            completion_tokens_details=completion_details,
            prompt_tokens_details=prompt_details,
        )
        self.assertEqual(usage.completion_tokens_details.accepted_prediction_tokens, 1)
        self.assertEqual(usage.completion_tokens_details.audio_tokens, 2)
        self.assertEqual(usage.completion_tokens_details.reasoning_tokens, 3)
        self.assertEqual(usage.completion_tokens_details.rejected_prediction_tokens, 0)
        self.assertEqual(usage.prompt_tokens_details.audio_tokens, 0)
        self.assertEqual(usage.prompt_tokens_details.cached_tokens, 4)
        self.assertEqual(usage.total_tokens, 15)
        self.assertEqual(usage.completion_tokens, 10)
        self.assertEqual(usage.prompt_tokens, 5)

    def test_get_outputs_from_grpc_response_populates_model_and_usage(self):
        """_get_outputs_from_grpc_response sets model and usage when present on proto."""
        from unittest import mock

        # Build a mock proto response with one output that has model and usage
        mock_usage = mock.Mock()
        mock_usage.completion_tokens = 20
        mock_usage.prompt_tokens = 8
        mock_usage.total_tokens = 28
        mock_usage.completion_tokens_details = None
        mock_usage.prompt_tokens_details = None

        mock_choice_msg = mock.Mock()
        mock_choice_msg.content = 'Hello'
        mock_choice_msg.tool_calls = []

        mock_choice = mock.Mock()
        mock_choice.finish_reason = 'stop'
        mock_choice.index = 0
        mock_choice.message = mock_choice_msg

        mock_output = mock.Mock()
        mock_output.model = 'gpt-4o-mini'
        mock_output.usage = mock_usage
        mock_output.choices = [mock_choice]

        mock_response = mock.Mock()
        mock_response.outputs = [mock_output]

        outputs = _get_outputs_from_grpc_response(mock_response)
        self.assertEqual(len(outputs), 1)
        out = outputs[0]
        self.assertEqual(out.model, 'gpt-4o-mini')
        self.assertIsNotNone(out.usage)
        self.assertEqual(out.usage.completion_tokens, 20)
        self.assertEqual(out.usage.prompt_tokens, 8)
        self.assertEqual(out.usage.total_tokens, 28)
        self.assertEqual(len(out.choices), 1)
        self.assertEqual(out.choices[0].message.content, 'Hello')

    def test_get_outputs_from_grpc_response_without_model_usage(self):
        """_get_outputs_from_grpc_response leaves model and usage None when absent."""
        from unittest import mock

        mock_choice_msg = mock.Mock()
        mock_choice_msg.content = 'Echo'
        mock_choice_msg.tool_calls = []

        mock_choice = mock.Mock()
        mock_choice.finish_reason = 'stop'
        mock_choice.index = 0
        mock_choice.message = mock_choice_msg

        mock_output = mock.Mock(spec=['choices'])
        mock_output.choices = [mock_choice]
        # No model or usage attributes

        mock_response = mock.Mock()
        mock_response.outputs = [mock_output]

        outputs = _get_outputs_from_grpc_response(mock_response)
        self.assertEqual(len(outputs), 1)
        out = outputs[0]
        self.assertIsNone(out.model)
        self.assertIsNone(out.usage)
        self.assertEqual(out.choices[0].message.content, 'Echo')


class ConverseAlpha2ResponseFormatTests(unittest.TestCase):
    """Unit tests for converse_alpha2 response_format parameter."""

    def test_converse_alpha2_passes_response_format_on_request(self):
        """converse_alpha2 sets response_format on the gRPC request when provided."""
        user_message = create_user_message('Structured output please')
        input_alpha2 = ConversationInputAlpha2(messages=[user_message])
        response_format = Struct()
        response_format.update(
            {'type': 'json_schema', 'json_schema': {'name': 'test', 'schema': {}}}
        )

        captured_requests = []
        mock_choice_msg = Mock()
        mock_choice_msg.content = 'ok'
        mock_choice_msg.tool_calls = []
        mock_choice = Mock()
        mock_choice.finish_reason = 'stop'
        mock_choice.index = 0
        mock_choice.message = mock_choice_msg
        mock_output = Mock()
        mock_output.choices = [mock_choice]
        mock_response = Mock()
        mock_response.outputs = [mock_output]
        mock_response.context_id = ''
        mock_call = Mock()

        def capture_run_rpc(rpc, request, *args, **kwargs):
            captured_requests.append(request)
            return (mock_response, mock_call)

        with patch('dapr.clients.health.DaprHealth.wait_for_sidecar'):
            client = DaprClient('localhost:50011')
        with patch.object(client.retry_policy, 'run_rpc', side_effect=capture_run_rpc):
            client.converse_alpha2(
                name='test-llm',
                inputs=[input_alpha2],
                response_format=response_format,
            )

        self.assertEqual(len(captured_requests), 1)
        req = captured_requests[0]
        self.assertTrue(hasattr(req, 'response_format'))
        self.assertEqual(req.response_format['type'], 'json_schema')
        self.assertEqual(req.response_format['json_schema']['name'], 'test')


class ExecuteRegisteredToolSyncTests(unittest.TestCase):
    def tearDown(self):
        # Cleanup all tools we may have registered by name prefix
        # (names are randomized per test to avoid collisions)
        pass  # Names are unique per test; we explicitly unregister in tests

    def test_sync_success_with_kwargs_and_sequence_and_json(self):
        name = f'test_add_{uuid.uuid4().hex[:8]}'

        @tool_decorator(name=name)
        def add(a: int, b: int) -> int:
            return a + b

        try:
            # kwargs mapping
            out = execute_registered_tool(name, {'a': 2, 'b': 3})
            self.assertEqual(out, 5)

            # sequence args
            out2 = execute_registered_tool(name, [10, 5])
            self.assertEqual(out2, 15)

            # JSON string params
            out3 = execute_registered_tool(name, json.dumps({'a': '7', 'b': '8'}))
            self.assertEqual(out3, 15)
        finally:
            unregister_tool(name)

    def test_sync_invalid_params_type_raises(self):
        name = f'test_echo_{uuid.uuid4().hex[:8]}'

        @tool_decorator(name=name)
        def echo(x: str) -> str:
            return x

        try:
            with self.assertRaises(ToolArgumentError):
                execute_registered_tool(name, 123)  # not Mapping/Sequence/None
        finally:
            unregister_tool(name)

    def test_sync_unregistered_tool_raises(self):
        name = f'does_not_exist_{uuid.uuid4().hex[:8]}'
        with self.assertRaises(ToolNotFoundError):
            execute_registered_tool(name, {'a': 1})

    def test_sync_tool_exception_wrapped(self):
        name = f'test_fail_{uuid.uuid4().hex[:8]}'

        @tool_decorator(name=name)
        def fail() -> None:
            raise ValueError('boom')

        try:
            with self.assertRaises(ToolExecutionError):
                execute_registered_tool(name)
        finally:
            unregister_tool(name)


class ExecuteRegisteredToolAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        # Nothing persistent; individual tests unregister.
        pass

    async def test_async_success_and_json_params(self):
        name = f'test_async_echo_{uuid.uuid4().hex[:8]}'

        @tool_decorator(name=name)
        async def echo(value: str) -> str:
            await asyncio.sleep(0)
            return value

        try:
            out = await execute_registered_tool_async(name, {'value': 'hi'})
            self.assertEqual(out, 'hi')

            out2 = await execute_registered_tool_async(name, json.dumps({'value': 'ok'}))
            self.assertEqual(out2, 'ok')
        finally:
            unregister_tool(name)

    async def test_async_invalid_params_type_raises(self):
        name = f'test_async_inv_{uuid.uuid4().hex[:8]}'

        @tool_decorator(name=name)
        async def one(x: int) -> int:
            return x

        try:
            with self.assertRaises(ToolArgumentError):
                await execute_registered_tool_async(name, 3.14)  # invalid type
        finally:
            unregister_tool(name)

    async def test_async_unregistered_tool_raises(self):
        name = f'does_not_exist_{uuid.uuid4().hex[:8]}'
        with self.assertRaises(ToolNotFoundError):
            await execute_registered_tool_async(name, None)

    async def test_async_tool_exception_wrapped(self):
        name = f'test_async_fail_{uuid.uuid4().hex[:8]}'

        @tool_decorator(name=name)
        async def fail_async() -> None:
            await asyncio.sleep(0)
            raise RuntimeError('nope')

        try:
            with self.assertRaises(ToolExecutionError):
                await execute_registered_tool_async(name)
        finally:
            unregister_tool(name)


if __name__ == '__main__':
    unittest.main()
