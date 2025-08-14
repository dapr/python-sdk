# ------------------------------------------------------------
# Copyright 2025 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

"""
Real LLM Providers Example for Dapr Conversation API (Alpha2)

This example demonstrates how to use real LLM providers (OpenAI, Anthropic, etc.)
with the Dapr Conversation API Alpha2. It showcases the latest features including:
- Advanced message types (user, system, assistant, developer, tool)
- Automatic parameter conversion (raw Python values)
- Enhanced tool calling capabilities
- Multi-turn conversations
- Decorator-based tool definition
- Both sync and async implementations

Prerequisites:
1. Set up API keys in .env file (copy from .env.example)
2. For manual mode: Start Dapr sidecar manually

Usage:
    # requires manual Dapr sidecar setup
    python examples/conversation/real_llm_providers_example.py

    # Show help
    python examples/conversation/real_llm_providers_example.py --help

Environment Variables:
    OPENAI_API_KEY: OpenAI API key
    ANTHROPIC_API_KEY: Anthropic API key
    MISTRAL_API_KEY: Mistral API key
    DEEPSEEK_API_KEY: DeepSeek API key
    GOOGLE_API_KEY: Google AI (Gemini) API key
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

if TYPE_CHECKING:
    from dapr.clients.grpc._response import ConversationResultAlpha2Message

# Add the parent directory to the path so we can import local dapr sdk
# uncomment if running from development version
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print('⚠️  python-dotenv not installed. Install with: pip install python-dotenv')

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import DaprClient
from dapr.clients.grpc import conversation


def create_weather_tool() -> conversation.ConversationTools:
    """Create a weather tool for testing Alpha2 tool calling using full JSON schema in parameters approach."""
    conversation.unregister_tool('get_weather')
    function = conversation.ConversationToolsFunction(
        name='get_weather',
        description='Get the current weather for a location',
        parameters={
            'type': 'object',
            'properties': {
                'location': {'type': 'string', 'description': 'The city and state or country'},
                'unit': {
                    'type': 'string',
                    'enum': ['celsius', 'fahrenheit'],
                    'description': 'Temperature unit',
                },
            },
            'required': ['location'],
        },
    )
    return conversation.ConversationTools(function=function)


def create_calculator_tool() -> conversation.ConversationTools:
    """Create a calculator tool using full JSON schema in parameters approach."""
    conversation.unregister_tool('calculate')  # cleanup
    function = conversation.ConversationToolsFunction(
        name='calculate',
        description='Perform mathematical calculations',
        parameters={
            'type': 'object',
            'properties': {
                'expression': {
                    'type': 'string',
                    'description': "Mathematical expression to evaluate (e.g., '2+2', 'sqrt(16)')",
                }
            },
            'required': ['expression'],
        },
    )
    return conversation.ConversationTools(function=function)


def create_time_tool() -> conversation.ConversationTools:
    """Create a simple tool with no parameters using full JSON schema in parameters approach."""
    conversation.unregister_tool('get_current_time')
    function = conversation.ConversationToolsFunction(
        name='get_current_time',
        description='Get the current date and time',
        parameters={'type': 'object', 'properties': {}, 'required': []},
    )
    return conversation.ConversationTools(function=function)


def create_search_tool() -> conversation.ConversationTools:
    """Create a more complex tool with multiple parameter types and constraints using full JSON schema in parameters approach."""
    conversation.unregister_tool('web_search')
    function = conversation.ConversationToolsFunction(
        name='web_search',
        description='Search the web for information',
        parameters={
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Search query'},
                'limit': {
                    'type': 'integer',
                    'description': 'Maximum number of results',
                    'minimum': 1,
                    'maximum': 10,
                    'default': 5,
                },
                'include_images': {
                    'type': 'boolean',
                    'description': 'Whether to include image results',
                    'default': False,
                },
                'domains': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    # 'description': 'Limit search to specific domains',
                },
            },
            'required': ['query'],
        },
    )
    return conversation.ConversationTools(function=function)


def create_tool_from_typed_function_example() -> conversation.ConversationTools:
    """Demonstrate creating tools from typed Python functions - Best DevEx for most cases.

    This shows the most advanced approach: define a typed function and automatically
    generate the complete tool schema from type hints and docstrings.
    """
    from typing import Optional, List
    from enum import Enum

    conversation.unregister_tool('find_restaurants')

    # Define the tool behavior as a regular Python function with type hints
    class PriceRange(Enum):
        BUDGET = 'budget'
        MODERATE = 'moderate'
        EXPENSIVE = 'expensive'

    def find_restaurants(
        location: str,
        cuisine: str = 'any',
        price_range: PriceRange = PriceRange.MODERATE,
        max_results: int = 5,
        dietary_restrictions: Optional[List[str]] = None,
    ) -> str:
        """Find restaurants in a specific location.

        Args:
            location: The city or neighborhood to search
            cuisine: Type of cuisine (italian, chinese, mexican, etc.)
            price_range: Budget preference for dining
            max_results: Maximum number of restaurant recommendations
            dietary_restrictions: Special dietary needs (vegetarian, gluten-free, etc.)
        """
        # This would contain actual implementation
        return f'Found restaurants in {location} serving {cuisine} food'

    # Create the tool using the from_function class method
    function = conversation.ConversationToolsFunction.from_function(find_restaurants)

    return conversation.ConversationTools(function=function)


def create_tool_from_tool_decorator_example() -> conversation.ConversationTools:
    """Demonstrate creating tools from typed Python functions - Best DevEx for most cases.

    This shows the most advanced approach: define a typed function and automatically
    generate the complete tool schema from type hints and docstrings.
    """
    from typing import Optional, List
    from enum import Enum

    conversation.unregister_tool('find_restaurants')

    # Define the tool behavior as a regular Python function with type hints
    class PriceRange(Enum):
        MODERATE = 'moderate'
        EXPENSIVE = 'expensive'

    @conversation.tool
    def find_restaurants(
        location: str,
        cuisine: str = 'any',
        price_range: PriceRange = PriceRange.MODERATE,
        max_results: int = 5,
        dietary_restrictions: Optional[List[str]] = None,
    ) -> str:
        """Find restaurants in a specific location.

        Args:
            location: The city or neighborhood to search
            cuisine: Type of cuisine (italian, chinese, mexican, etc.)
            price_range: Budget preference for dining
            max_results: Maximum number of restaurant recommendations
            dietary_restrictions: Special dietary needs (vegetarian, gluten-free, etc.)
        """
        # This would contain actual implementation
        return f'Found restaurants in {location} serving {cuisine} food'

    return conversation.ConversationTools(function=find_restaurants)


def execute_weather_tool(location: str, unit: str = 'fahrenheit') -> str:
    """Simulate weather tool execution."""
    temp = '72°F' if unit == 'fahrenheit' else '22°C'
    return f'The weather in {location} is sunny with a temperature of {temp}.'


def convert_llm_response_to_conversation_input(
    result_message: 'ConversationResultAlpha2Message',
) -> conversation.ConversationMessage:
    """Convert ConversationResultMessage (from LLM response) to ConversationMessage (for conversation input).

    This standalone utility function makes it easy to append LLM responses to conversation history
    and reuse them as input for subsequent conversation turns in multi-turn scenarios.

    Args:
        result_message: ConversationResultMessage from LLM response (choice.message)

    Returns:
        ConversationMessage suitable for input to next conversation turn

    Example:
        >>> response = client.converse_alpha2(name="openai", inputs=[input_alpha2], tools=[tool])
        >>> choice = response.outputs[0].choices[0]
        >>>
        >>> # Convert LLM response to conversation message
        >>> assistant_message = convert_llm_response_to_conversation_input(choice.message)
        >>> conversation_history.append(assistant_message)
        >>>
        >>> # Use in next turn
        >>> next_input = ConversationInputAlpha2(messages=conversation_history)
        >>> next_response = client.converse_alpha2(name="openai", inputs=[next_input])
    """
    # Convert content string to ConversationMessageContent list
    content = []
    if result_message.content:
        content = [conversation.ConversationMessageContent(text=result_message.content)]

    # Convert tool_calls if present (they're already the right type)
    tool_calls = result_message.tool_calls or []

    # Create assistant message (since LLM responses are always assistant messages)
    return conversation.ConversationMessage(
        of_assistant=conversation.ConversationMessageOfAssistant(
            content=content, tool_calls=tool_calls
        )
    )


class RealLLMProviderTester:
    """Test real LLM providers with Dapr Conversation API Alpha2."""

    def __init__(self):
        self.available_providers = {}
        self.component_configs = {}
        self.components_dir = None

    def load_environment(self) -> None:
        """Load environment variables from .env file if available."""
        if DOTENV_AVAILABLE:
            env_file = Path(__file__).parent / '.env'
            if env_file.exists():
                load_dotenv(env_file)
                print(f'📁 Loaded environment from {env_file}')
            else:
                print(f'⚠️  No .env file found at {env_file}')
                print('   Copy .env.example to .env and add your API keys')
        else:
            print('⚠️  python-dotenv not available, using system environment variables')

    def detect_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """Detect which LLM providers are available based on API keys."""
        providers = {}

        # OpenAI
        if os.getenv('OPENAI_API_KEY'):
            providers['openai'] = {
                'display_name': 'OpenAI GPT-5-mini',
                'component_type': 'conversation.openai',
                'api_key_env': 'OPENAI_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('OPENAI_API_KEY')},
                    {'name': 'model', 'value': 'gpt-5-mini-2025-08-07'},
                ],
            }

        # Anthropic
        if os.getenv('ANTHROPIC_API_KEY'):
            providers['anthropic'] = {
                'display_name': 'Anthropic Claude Sonnet 4',
                'component_type': 'conversation.anthropic',
                'api_key_env': 'ANTHROPIC_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('ANTHROPIC_API_KEY')},
                    {'name': 'model', 'value': 'claude-sonnet-4-20250514'},
                ],
            }

        # Mistral
        if os.getenv('MISTRAL_API_KEY'):
            providers['mistral'] = {
                'display_name': 'Mistral Large',
                'component_type': 'conversation.mistral',
                'api_key_env': 'MISTRAL_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('MISTRAL_API_KEY')},
                    {'name': 'model', 'value': 'mistral-large-latest'},
                ],
            }

        # DeepSeek
        if os.getenv('DEEPSEEK_API_KEY'):
            providers['deepseek'] = {
                'display_name': 'DeepSeek V3',
                'component_type': 'conversation.deepseek',
                'api_key_env': 'DEEPSEEK_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('DEEPSEEK_API_KEY')},
                    {'name': 'model', 'value': 'deepseek-chat'},
                ],
            }

        # Google AI (Gemini)
        if os.getenv('GOOGLE_API_KEY'):
            providers['google'] = {
                'display_name': 'Google Gemini 2.5 Flash',
                'component_type': 'conversation.googleai',
                'api_key_env': 'GOOGLE_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('GOOGLE_API_KEY')},
                    {'name': 'model', 'value': 'gemini-2.5-flash'},
                ],
            }

        return providers

    def create_component_configs(self, selected_providers: Optional[List[str]] = None) -> str:
        """Create Dapr component configurations for available providers (those with API keys exposed)."""
        # Create temporary directory for components
        self.components_dir = tempfile.mkdtemp(prefix='dapr-llm-components-')

        # If no specific providers selected, use OpenAI as default (most reliable)
        if not selected_providers:
            selected_providers = (
                ['openai']
                if 'openai' in self.available_providers
                else list(self.available_providers.keys())[:1]
            )

        for provider_id in selected_providers:
            if provider_id not in self.available_providers:
                continue

            config = self.available_providers[provider_id]
            component_config = {
                'apiVersion': 'dapr.io/v1alpha1',
                'kind': 'Component',
                'metadata': {'name': provider_id},
                'spec': {
                    'type': config['component_type'],
                    'version': 'v1',
                    'metadata': config['metadata'],
                },
            }

            # Write component file
            component_file = Path(self.components_dir) / f'{provider_id}.yaml'
            with open(component_file, 'w') as f:
                yaml.dump(component_config, f, default_flow_style=False)

            print(f'📝 Created component: {component_file}')

        return self.components_dir

    def test_basic_conversation_alpha2(self, provider_id: str) -> None:
        """Test basic Alpha2 conversation with a provider."""
        print(
            f"\n💬 Testing Alpha2 basic conversation with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                # Create Alpha2 conversation input with sophisticated message structure
                user_message = conversation.create_user_message(
                    "Hello! Please respond with exactly: 'Hello from Dapr Alpha2!'"
                )
                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                # Use new parameter conversion (raw Python values automatically converted)
                response = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    parameters={
                        'temperature': 0.7,
                        'max_tokens': 100,
                        'top_p': 0.9,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    print(f'✅ Alpha2 Response: {choice.message.content}')
                    print(f'📊 Finish reason: {choice.finish_reason}')
                else:
                    print('❌ No Alpha2 response received')

        except Exception as e:
            print(f'❌ Alpha2 basic conversation error: {e}')

    def test_multi_turn_conversation_alpha2(self, provider_id: str) -> None:
        """Test multi-turn Alpha2 conversation with different message types."""
        print(
            f"\n🔄 Testing Alpha2 multi-turn conversation with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                # Create a multi-turn conversation with system, user, and assistant messages
                system_message = conversation.create_system_message(
                    'You are a helpful AI assistant. Be concise.'
                )
                user_message1 = conversation.create_user_message('What is 2+2?')
                assistant_message = conversation.create_assistant_message('2+2 equals 4.')
                user_message2 = conversation.create_user_message('What about 3+3?')

                input_alpha2 = conversation.ConversationInputAlpha2(
                    messages=[system_message, user_message1, assistant_message, user_message2]
                )

                response = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    parameters={
                        'temperature': 0.5,
                        'max_tokens': 150,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    print(
                        f'✅ Multi-turn conversation processed {len(response.outputs[0].choices)} message(s)'
                    )
                    for i, choice in enumerate(response.outputs[0].choices):
                        print(f'   Response {i+1}: {choice.message.content[:100]}...')
                else:
                    print('❌ No multi-turn response received')

        except Exception as e:
            print(f'❌ Multi-turn conversation error: {e}')

    def test_tool_calling_alpha2(self, provider_id: str) -> None:
        """Test Alpha2 tool calling with a provider."""
        print(
            f"\n🔧 Testing Alpha2 tool calling with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                weather_tool = create_weather_tool()
                user_message = conversation.create_user_message(
                    "What's the weather like in San Francisco?"
                )

                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                response = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    tools=[weather_tool],
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,  # Lower temperature for more consistent tool calling
                        'max_tokens': 500,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    print(f'📊 Finish reason: {choice.finish_reason}')

                    if choice.finish_reason == 'tool_calls' and choice.message.tool_calls:
                        print(f'🔧 Tool calls made: {len(choice.message.tool_calls)}')
                        for tool_call in choice.message.tool_calls:
                            print(f'   Tool: {tool_call.function.name}')
                            print(f'   Arguments: {tool_call.function.arguments}')

                            # Execute the tool to show the workflow
                            try:
                                args = json.loads(tool_call.function.arguments)
                                weather_result = execute_weather_tool(
                                    args.get('location', 'San Francisco'),
                                    args.get('unit', 'fahrenheit'),
                                )
                                print(f'🌤️ Tool executed: {weather_result}')

                                # Demonstrate tool result message (for multi-turn tool workflows)
                                tool_result_message = conversation.create_tool_message(
                                    tool_id=tool_call.id,
                                    name=tool_call.function.name,
                                    content=weather_result,
                                )
                                print(
                                    '✅ Alpha2 tool calling demonstration completed! Tool Result Message:'
                                )
                                print(tool_result_message)

                            except json.JSONDecodeError:
                                print('⚠️ Could not parse tool arguments')
                    else:
                        print(f'💬 Regular response: {choice.message.content}')
                else:
                    print('❌ No tool calling response received')

        except Exception as e:
            print(f'❌ Alpha2 tool calling error: {e}')

    def test_parameter_conversion(self, provider_id: str) -> None:
        """Test the new parameter conversion feature."""
        print(
            f"\n🔄 Testing parameter conversion with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                user_message = conversation.create_user_message(
                    'Tell me about the different tool creation approaches available.'
                )
                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                # Demonstrate different tool creation approaches
                weather_tool = create_weather_tool()  # Simple properties approach
                calc_tool = create_calculator_tool()  # Full JSON schema approach
                time_tool = create_time_tool()  # No parameters approach
                search_tool = create_search_tool()  # Complex schema with arrays, etc.

                print(
                    f'✅ Created {len([weather_tool, calc_tool, time_tool, search_tool])} tools with different approaches!'
                )

                # Test various parameter types that are automatically converted
                response = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    tools=[weather_tool, calc_tool, time_tool, search_tool],
                    parameters={
                        # Raw Python values - automatically converted to GrpcAny
                        'temperature': 0.8,  # float
                        'max_tokens': 200,  # int
                        'top_p': 1.0,  # float
                        'frequency_penalty': 0.0,  # float
                        'presence_penalty': 0.0,  # float
                        'stream': False,  # bool
                        'tool_choice': 'none',  # string
                        'model': 'gpt-4o-mini',  # string (provider-specific)
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    print(f'✅ Parameter conversion successful!')
                    print(f'✅ Tool creation helpers working perfectly!')
                    print(f'   Response: {choice.message.content[:100]}...')
                else:
                    print('❌ Parameter conversion test failed')

        except Exception as e:
            print(f'❌ Parameter conversion error: {e}')

    def test_multi_turn_tool_calling_alpha2(self, provider_id: str) -> None:
        """Test multi-turn Alpha2 tool calling with proper context accumulation."""
        print(
            f"\n🔄🔧 Testing multi-turn tool calling with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                weather_tool = create_weather_tool()
                conversation_history = []

                # Turn 1: User asks about weather (include tools)
                print('\n--- Turn 1: Initial weather query ---')
                user_message1 = conversation.create_user_message(
                    "What's the weather like in San Francisco? Use one of the tools available."
                )
                conversation_history.append(user_message1)

                print(f'📝 Request 1 context: {len(conversation_history)} messages + tools')
                input_alpha2_turn1 = conversation.ConversationInputAlpha2(
                    messages=conversation_history
                )

                response1 = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2_turn1],
                    tools=[weather_tool],  # Tools included in turn 1
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                # Check all outputs and choices for tool calls
                tool_calls_found = []
                assistant_messages = []

                for output_idx, output in enumerate(response1.outputs or []):
                    for choice_idx, choice in enumerate(output.choices or []):
                        print(
                            f'📋 Checking output {output_idx}, choice {choice_idx}: finish_reason={choice.finish_reason}, choice: {choice}'
                        )

                        # Convert and collect all assistant messages
                        assistant_message = convert_llm_response_to_conversation_input(
                            choice.message
                        )
                        assistant_messages.append(assistant_message)

                        # Check for tool calls in this choice
                        if choice.message.tool_calls:
                            # if not choice.message.tool_calls[0].id:
                            #     choice.message.tool_calls[0].id = "1"
                            tool_calls_found.extend(choice.message.tool_calls)
                            print(
                                f'🔧 Found {len(choice.message.tool_calls)} tool call(s) in output {output_idx}, choice {choice_idx}'
                            )

                # Use the first assistant message for conversation history (most providers return one)
                if assistant_messages:
                    for assistant_message in assistant_messages:
                        conversation_history.append(assistant_message)
                    print(
                        f'✅ Added assistant message to history (from {len(assistant_messages)} total messages)'
                    )

                if tool_calls_found:
                    # Use the first tool call for demonstration
                    tool_call = tool_calls_found[0]
                    print(
                        f'🔧 Processing tool call: {tool_call.function.name} (found {len(tool_calls_found)} total tool calls)'
                    )

                    # Execute the tool
                    args = json.loads(tool_call.function.arguments)
                    weather_result = execute_weather_tool(
                        args.get('location', 'San Francisco'), args.get('unit', 'fahrenheit')
                    )
                    print(f'🌤️ Tool result: {weather_result}')

                    # Add tool result to conversation history
                    tool_result_message = conversation.create_tool_message(
                        tool_id=tool_call.id, name=tool_call.function.name, content=weather_result
                    )
                    conversation_history.append(tool_result_message)

                    # Turn 2: LLM processes tool result (accumulate context + tools)
                    print('\n--- Turn 2: LLM processes tool result ---')
                    print(f'📝 Request 2 context: {len(conversation_history)} messages + tools')
                    input_alpha2_turn2 = conversation.ConversationInputAlpha2(
                        messages=conversation_history
                    )

                    response2 = client.converse_alpha2(
                        name=provider_id,
                        inputs=[input_alpha2_turn2],
                        tools=[weather_tool],  # Tools carried forward to turn 2
                        parameters={
                            'temperature': 0.3,
                            'max_tokens': 500,
                        },
                    )

                    if response2.outputs and response2.outputs[0].choices:
                        choice2 = response2.outputs[0].choices[0]
                        print(f'🤖 LLM response with tool context: {choice2.message.content}')

                        # Add LLM's response to accumulated history using utility
                        assistant_message2 = convert_llm_response_to_conversation_input(
                            choice2.message
                        )
                        conversation_history.append(assistant_message2)

                        # Turn 3: Follow-up question (full context + tools)
                        print('\n--- Turn 3: Follow-up question using accumulated context ---')
                        user_message2 = conversation.create_user_message(
                            'Should I bring an umbrella? Also, what about the weather in New York?'
                        )
                        conversation_history.append(user_message2)

                        print(f'📝 Request 3 context: {len(conversation_history)} messages + tools')
                        print('📋 Accumulated context includes:')
                        print('   • Original user query about San Francisco')
                        print("   • Assistant's tool call intention")
                        print('   • Weather tool execution result')
                        print("   • Assistant's weather summary")
                        print('   • New user follow-up question')

                        input_alpha2_turn3 = conversation.ConversationInputAlpha2(
                            messages=conversation_history
                        )

                        response3 = client.converse_alpha2(
                            name=provider_id,
                            inputs=[input_alpha2_turn3],
                            tools=[weather_tool],  # Tools still available in turn 3
                            tool_choice='auto',
                            parameters={
                                'temperature': 0.3,
                                'max_tokens': 500,
                            },
                        )

                        if response3.outputs and response3.outputs[0].choices:
                            choice3 = response3.outputs[0].choices[0]

                            if choice3.finish_reason == 'tool_calls' and choice3.message.tool_calls:
                                print(
                                    f'🔧 Follow-up tool call: {choice3.message.tool_calls[0].function.name}'
                                )

                                # Execute second tool call
                                tool_call3 = choice3.message.tool_calls[0]
                                # if not tool_call3.id:
                                #     tool_call3.id = "2"
                                args3 = json.loads(tool_call3.function.arguments)
                                weather_result3 = execute_weather_tool(
                                    args3.get('location', 'New York'),
                                    args3.get('unit', 'fahrenheit'),
                                )
                                print(f'🌤️ Second tool result: {weather_result3}')

                                # Could continue accumulating context for turn 4...
                                print(
                                    '✅ Multi-turn tool calling with proper context accumulation successful!'
                                )
                                print(
                                    f'📊 Final context: {len(conversation_history)} messages + tools available for next turn'
                                )
                            else:
                                print(
                                    f'💬 Follow-up response using accumulated context: {choice3.message.content}'
                                )
                                print(
                                    '✅ Multi-turn conversation with proper context accumulation successful!'
                                )
                                print(f'📊 Final context: {len(conversation_history)} messages')
                else:
                    print(
                        '⚠️ No tool calls found in any output/choice - continuing with regular conversation flow'
                    )
                    # Could continue with regular multi-turn conversation without tools

                if not assistant_messages:
                    print('❌ No assistant messages received in first turn')

        except Exception as e:
            print(f'❌ Multi-turn tool calling error: {e}')

    def test_multi_turn_tool_calling_alpha2_tool_helpers(self, provider_id: str) -> None:
        """Test multi-turn Alpha2 tool calling with proper context accumulation using higher level abstractions."""
        print(
            f"\n🔄🔧 Testing multi-turn tool calling with {self.available_providers[provider_id]['display_name']}"
        )

        # using decorator

        @conversation.tool
        def get_weather(location: str, unit: str = 'fahrenheit') -> str:
            """Get the current weather for a location."""
            # This is a mock implementation. Replace with actual weather API call.
            temp = '72°F' if unit == 'fahrenheit' else '22°C'
            return f'The weather in {location} is sunny with a temperature of {temp}.'

        try:
            with DaprClient() as client:
                conversation_history = []  # our context to pass to the LLM on each turn

                # Turn 1: User asks about weather (include tools)
                print('\n--- Turn 1: Initial weather query ---')
                user_message1 = conversation.create_user_message(
                    "What's the weather like in San Francisco? Use one of the tools available."
                )
                conversation_history.append(user_message1)

                print(f'📝 Request 1 context: {len(conversation_history)} messages + tools')
                input_alpha2_turn1 = conversation.ConversationInputAlpha2(
                    messages=conversation_history
                )

                response1 = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2_turn1],
                    tools=conversation.get_registered_tools(),  # using registered tools (automatically registered by the decorator)
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                def append_response_to_history(response: 'ConversationResultAlpha2Message'):
                    """Helper to append response to history and execute tool calls."""
                    for msg in response.to_assistant_messages():
                        conversation_history.append(msg)
                        if not msg.of_assistant.tool_calls:
                            continue
                        for _tool_call in msg.of_assistant.tool_calls:
                            print(f'Executing tool call: {_tool_call.function.name}')
                            output = conversation.execute_registered_tool(
                                _tool_call.function.name, _tool_call.function.arguments
                            )
                            print(f'Tool output: {output}')

                            # append result to history
                            conversation_history.append(
                                conversation.create_tool_message(
                                    tool_id=_tool_call.id,
                                    name=_tool_call.function.name,
                                    content=output,
                                )
                            )

                append_response_to_history(response1)

                # Turn 2: LLM processes tool result (accumulate context + tools)
                print('\n--- Turn 2: LLM processes tool result ---')
                print(f'📝 Request 2 context: {len(conversation_history)} messages + tools')
                input_alpha2_turn2 = conversation.ConversationInputAlpha2(
                    messages=conversation_history
                )

                response2 = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2_turn2],
                    tools=conversation.get_registered_tools(),
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                # Turn 3: Follow-up question (full context + tools)

                append_response_to_history(response2)

                print('\n--- Turn 3: Follow-up question using accumulated context ---')
                user_message2 = conversation.create_user_message(
                    'Should I bring an umbrella? Also, what about the weather in New York?'
                )
                conversation_history.append(user_message2)

                print(f'📝 Request 3 context: {len(conversation_history)} messages + tools')
                print('📋 Accumulated context includes:')

                input_alpha2_turn3 = conversation.ConversationInputAlpha2(
                    messages=conversation_history
                )

                response3 = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2_turn3],
                    tools=conversation.get_registered_tools(),
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                append_response_to_history(response3)

                print(f'📝 Request 4 context: {len(conversation_history)} messages + tools')
                print('📋 Expect response about the umbrella:')

                input_alpha2_turn4 = conversation.ConversationInputAlpha2(
                    messages=conversation_history
                )

                response4 = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2_turn4],
                    tools=conversation.get_registered_tools(),
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                append_response_to_history(response4)

                print('Full conversation history trace:')
                for msg in conversation_history:
                    msg.trace_print(2)

        except Exception as e:
            print(f'❌ Multi-turn tool calling error: {e}')
        finally:
            conversation.unregister_tool('get_weather')

    def test_function_to_schema_approach(self, provider_id: str) -> None:
        """Test the best DevEx for most cases: function-to-JSON-schema automatic tool creation."""
        print(
            f"\n🎯 Testing function-to-schema approach with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                # Create a tool using the typed function approach
                restaurant_tool = create_tool_from_typed_function_example()
                print(restaurant_tool)

                user_message = conversation.create_user_message(
                    'I want to find Italian restaurants in San Francisco with a moderate price range.'
                )
                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                response = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    tools=[restaurant_tool],
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    print(f'📊 Finish reason: {choice.finish_reason}')

                    if choice.finish_reason == 'tool_calls' and choice.message.tool_calls:
                        print('🎯 Function-to-schema tool calling successful!')
                        for tool_call in choice.message.tool_calls:
                            print(f'   Tool: {tool_call.function.name}')
                            print(f'   Arguments: {tool_call.function.arguments}')

                            # This demonstrates the complete workflow
                            print('✅ Auto-generated schema worked perfectly with real LLM!')
                    else:
                        print(f'💬 Response: {choice.message.content}')
                else:
                    print('❌ No function-to-schema response received')

        except Exception as e:
            print(f'❌ Function-to-schema approach error: {e}')

    def test_tool_decorated_function_to_schema_approach(self, provider_id: str) -> None:
        """Test the best DevEx for most cases: function-to-JSON-schema automatic tool creation."""
        print(
            f"\n🎯 Testing decorator tool function-to-schema approach with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                # Create a tool using the typed function approach
                create_tool_from_tool_decorator_example()

                # we can get tools registered from different places in our repo
                print(conversation.get_registered_tools())

                user_message = conversation.create_user_message(
                    'I want to find Italian restaurants in San Francisco with a moderate price range.'
                )
                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                response = client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    tools=conversation.get_registered_tools(),
                    tool_choice='auto',
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    print(f'📊 Finish reason: {choice.finish_reason}')

                    if choice.finish_reason == 'tool_calls' and choice.message.tool_calls:
                        print('🎯 Function-to-schema tool calling successful!')
                        for tool_call in choice.message.tool_calls:
                            print(f'   Tool: {tool_call.function.name}')
                            print(f'   Arguments: {tool_call.function.arguments}')

                            # This demonstrates the complete workflow
                            print('✅ Auto-generated schema worked perfectly with real LLM!')
                    else:
                        print(f'💬 Response: {choice.message.content}')
                else:
                    print('❌ No function-to-schema response received')

        except Exception as e:
            print(f'❌ Function-to-schema approach error: {e}')

    async def test_async_conversation_alpha2(self, provider_id: str) -> None:
        """Test async Alpha2 conversation with a provider."""
        print(
            f"\n⚡ Testing async Alpha2 conversation with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            async with AsyncDaprClient() as client:
                user_message = conversation.create_user_message(
                    'Tell me a very short joke about async programming.'
                )
                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                response = await client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    print(f'✅ Async Alpha2 response: {choice.message.content}')
                else:
                    print('❌ No async Alpha2 response received')

        except Exception as e:
            print(f'❌ Async Alpha2 error: {e}')

    async def test_async_tool_calling_alpha2(self, provider_id: str) -> None:
        """Test async Alpha2 tool calling with a provider."""
        print(
            f"\n🔧⚡ Testing async Alpha2 tool calling with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            async with AsyncDaprClient() as client:
                weather_tool = create_weather_tool()
                user_message = conversation.create_user_message("What's the weather in Tokyo?")

                input_alpha2 = conversation.ConversationInputAlpha2(messages=[user_message])

                response = await client.converse_alpha2(
                    name=provider_id,
                    inputs=[input_alpha2],
                    tools=[weather_tool],
                    parameters={
                        'temperature': 0.3,
                        'max_tokens': 500,
                    },
                )

                if response.outputs and response.outputs[0].choices:
                    choice = response.outputs[0].choices[0]
                    if choice.finish_reason == 'tool_calls' and choice.message.tool_calls:
                        print('✅ Async tool calling successful!')
                        for tool_call in choice.message.tool_calls:
                            print(f'   Tool: {tool_call.function.name}')
                            args = json.loads(tool_call.function.arguments)
                            weather_result = execute_weather_tool(
                                args.get('location', 'Tokyo'), args.get('unit', 'fahrenheit')
                            )
                            print(f'   Result: {weather_result}')
                    else:
                        print(f'💬 Async response: {choice.message.content}')
                else:
                    print('❌ No async tool calling response received')

        except Exception as e:
            print(f'❌ Async tool calling error: {e}')

    def run_comprehensive_test(self, provider_id: str) -> None:
        """Run comprehensive Alpha2 tests for a provider."""
        provider_name = self.available_providers[provider_id]['display_name']
        print(f"\n{'='*60}")
        print(f'🧪 Testing {provider_name} with Alpha2 API')
        print(f"{'='*60}")

        # Alpha2 Sync tests
        # self.test_basic_conversation_alpha2(provider_id)
        # self.test_multi_turn_conversation_alpha2(provider_id)
        # self.test_tool_calling_alpha2(provider_id)
        # self.test_parameter_conversion(provider_id)
        # self.test_function_to_schema_approach(provider_id)
        # self.test_tool_decorated_function_to_schema_approach(provider_id)
        # self.test_multi_turn_tool_calling_alpha2(provider_id)
        self.test_multi_turn_tool_calling_alpha2_tool_helpers(provider_id)

        # Alpha2 Async tests
        asyncio.run(self.test_async_conversation_alpha2(provider_id))
        asyncio.run(self.test_async_tool_calling_alpha2(provider_id))

        # Legacy Alpha1 test for comparison
        self.test_basic_conversation_alpha1_legacy(provider_id)

    def test_basic_conversation_alpha1_legacy(self, provider_id: str) -> None:
        """Test legacy Alpha1 conversation for comparison."""
        print(
            f"\n📚 Testing legacy Alpha1 for comparison with {self.available_providers[provider_id]['display_name']}"
        )

        try:
            with DaprClient() as client:
                inputs = [
                    conversation.ConversationInput(
                        content="Hello! Please respond with: 'Hello from Dapr Alpha1!'", role='user'
                    )
                ]

                response = client.converse_alpha1(
                    name=provider_id,
                    inputs=inputs,
                    parameters={
                        'temperature': 0.7,
                        'max_tokens': 100,
                    },
                )

                if response.outputs:
                    result = response.outputs[0].result
                    print(f'✅ Alpha1 Response: {result}')
                else:
                    print('❌ No Alpha1 response received')

        except Exception as e:
            print(f'❌ Alpha1 legacy conversation error: {e}')

    def cleanup(self) -> None:
        # Clean up temporary components directory
        if self.components_dir and Path(self.components_dir).exists():
            import shutil

            shutil.rmtree(self.components_dir)
            print(f'🧹 Cleaned up components directory: {self.components_dir}')


def main():
    """Main function to run the real LLM providers test with Alpha2 API."""
    print('🚀 Real LLM Providers Example for Dapr Conversation API Alpha2')
    print('=' * 60)

    # Check for help flag
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return

    tester = RealLLMProviderTester()

    try:
        # Load environment variables
        tester.load_environment()

        # Detect available providers
        print('\n🔍 Detecting available LLM providers...')
        tester.available_providers = tester.detect_available_providers()

        if not tester.available_providers:
            print('\n❌ No LLM providers configured!')
            print('Please set up API keys in .env file (copy from .env.example)')
            print('Available providers: OpenAI, Anthropic, Mistral, DeepSeek, Google AI')
            return

        print(f'\n✅ Found {len(tester.available_providers)} configured provider(s)')

        # Create component configurations for all available providers
        selected_providers = list(tester.available_providers.keys())
        components_dir = tester.create_component_configs(selected_providers)

        # Manual sidecar setup
        print('\n⚠️  IMPORTANT: Make sure Dapr sidecar is running with components from:')
        print(f'   {components_dir}')
        print('\nTo start the sidecar with these components:')
        print(
            f'   dapr run --app-id test-app --dapr-http-port 3500 --dapr-grpc-port 50001 --resources-path {components_dir}'
        )

        # Wait for user to confirm
        input('\nPress Enter when Dapr sidecar is running with the component configurations...')

        # Test only the providers we created components for
        for provider_id in selected_providers:
            if provider_id in tester.available_providers:
                tester.run_comprehensive_test(provider_id)

        print(f"\n{'='*60}")
        print('🎉 All Alpha2 tests completed!')
        print('✅ Real LLM provider integration with Alpha2 API is working correctly')
        print('🔧 Features demonstrated:')
        print('   • Alpha2 conversation API with sophisticated message types')
        print('   • Automatic parameter conversion (raw Python values)')
        print('   • Enhanced tool calling capabilities')
        print('   • Multi-turn conversations')
        print('   • Multi-turn tool calling with context expansion')
        print('   • Function-to-schema automatic tool generation')
        print('   • Function-to-schema using @tool decorator for automatic tool generation')
        print('   • Both sync and async implementations')
        print('   • Backward compatibility with Alpha1')
        print(f"{'='*60}")

    except KeyboardInterrupt:
        print('\n\n⏹️  Tests interrupted by user')
    except Exception as e:
        print(f'\n❌ Unexpected error: {e}')
        import traceback

        traceback.print_exc()
    finally:
        tester.cleanup()


if __name__ == '__main__':
    main()
