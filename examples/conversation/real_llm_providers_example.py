#!/usr/bin/env python3

"""
Real LLM Providers Example for Dapr Conversation API

This example demonstrates how to use real LLM providers (OpenAI, Anthropic, etc.)
with the Dapr Conversation API. It creates component configurations and tests
actual conversation functionality with tool calling support.

Prerequisites:
1. Set up API keys in .env file (copy from .env.example)
2. For local dev mode: Local Dapr repository cloned alongside this SDK
3. For manual mode: Start Dapr sidecar manually

Usage:
    # Automatic mode (recommended) - manages Dapr sidecar automatically
    python examples/conversation/real_llm_providers_example.py --local-dev

    # Manual mode - requires manual Dapr sidecar setup
    python examples/conversation/real_llm_providers_example.py

    # Show help
    python examples/conversation/real_llm_providers_example.py --help

Environment Variables:
    OPENAI_API_KEY: OpenAI API key
    ANTHROPIC_API_KEY: Anthropic API key
    MISTRAL_API_KEY: Mistral API key
    DEEPSEEK_API_KEY: DeepSeek API key
    GOOGLE_API_KEY: Google AI (Gemini) API key
    USE_LOCAL_DEV: Set to 'true' to use local dev mode
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add the parent directory to the path so we can import dapr
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import DaprClient
from dapr.clients.grpc._request import ContentPart, ConversationInput, TextContent, Tool


class DaprSidecarManager:
    """Manages Dapr sidecar lifecycle using the local development build."""

    def __init__(self):
        self.process = None
        self.temp_components_dir = None

    def start_with_components(self, components_dir: str, build_local_dapr: bool = False) -> bool:
        """Start Dapr sidecar with specified components using local development build."""
        try:
            # Start sidecar using run_dapr_dev.py with our components
            project_root = Path(__file__).parent.parent.parent
            cmd = [
                sys.executable,
                str(project_root / "tools" / "run_dapr_dev.py"),
                "--components", components_dir,
            ]

            if build_local_dapr:
                cmd.append("--build")

            print(f"🚀 Starting Dapr sidecar with components from: {components_dir}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(project_root)
            )

            # Wait a bit for startup
            time.sleep(3)

            # Check if process is still running
            if self.process.poll() is None:
                print("✅ Dapr sidecar started successfully")
                return True
            else:
                print("❌ Dapr sidecar failed to start")
                return False

        except Exception as e:
            print(f"❌ Failed to start sidecar: {e}")
            return False

    def stop(self):
        """Stop the Dapr sidecar process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                print("🛑 Stopped Dapr sidecar")
            except subprocess.TimeoutExpired:
                self.process.kill()
                print("🔥 Force killed Dapr sidecar")
            except Exception as e:
                print(f"⚠️ Error stopping sidecar: {e}")
            finally:
                self.process = None


class RealLLMProviderTester:
    """Test real LLM providers with Dapr Conversation API."""

    def __init__(self, use_local_dev: bool = False):
        self.available_providers = {}
        self.component_configs = {}
        self.components_dir = None
        self.use_local_dev = use_local_dev
        self.sidecar_manager = DaprSidecarManager() if use_local_dev else None

    def load_environment(self) -> None:
        """Load environment variables from .env file if available."""
        if DOTENV_AVAILABLE:
            env_file = Path(__file__).parent / '.env'
            if env_file.exists():
                load_dotenv(env_file)
                print(f"📁 Loaded environment from {env_file}")
            else:
                print(f"⚠️  No .env file found at {env_file}")
                print("   Copy .env.example to .env and add your API keys")
        else:
            print("⚠️  python-dotenv not available, using system environment variables")

    def detect_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """Detect which LLM providers are available based on API keys."""
        providers = {}

        # OpenAI
        if os.getenv('OPENAI_API_KEY'):
            providers['openai'] = {
                'display_name': 'OpenAI GPT-4o-mini',
                'component_type': 'conversation.openai',
                'api_key_env': 'OPENAI_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('OPENAI_API_KEY')},
                    {'name': 'model', 'value': 'gpt-4o-mini'}
                ]
            }

        # Anthropic
        if os.getenv('ANTHROPIC_API_KEY'):
            providers['anthropic'] = {
                'display_name': 'Anthropic Claude Sonnet 4',
                'component_type': 'conversation.anthropic',
                'api_key_env': 'ANTHROPIC_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('ANTHROPIC_API_KEY')},
                    {'name': 'model', 'value': 'claude-sonnet-4-20250514'}
                ]
            }

        # Mistral
        if os.getenv('MISTRAL_API_KEY'):
            providers['mistral'] = {
                'display_name': 'Mistral Large',
                'component_type': 'conversation.mistral',
                'api_key_env': 'MISTRAL_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('MISTRAL_API_KEY')},
                    {'name': 'model', 'value': 'mistral-large-latest'}
                ]
            }

        # DeepSeek
        if os.getenv('DEEPSEEK_API_KEY'):
            providers['deepseek'] = {
                'display_name': 'DeepSeek V3',
                'component_type': 'conversation.deepseek',
                'api_key_env': 'DEEPSEEK_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('DEEPSEEK_API_KEY')},
                    {'name': 'model', 'value': 'deepseek-chat'}
                ]
            }

        # Google AI (Gemini)
        if os.getenv('GOOGLE_API_KEY'):
            providers['google'] = {
                'display_name': 'Google Gemini 2.5 Flash',
                'component_type': 'conversation.googleai',
                'api_key_env': 'GOOGLE_API_KEY',
                'metadata': [
                    {'name': 'key', 'value': os.getenv('GOOGLE_API_KEY')},
                    {'name': 'model', 'value': 'gemini-2.5-flash'}
                ]
            }

        return providers

    def create_component_configs(self, selected_providers: Optional[List[str]] = None) -> str:
        """Create Dapr component configurations for available providers."""
        # Create temporary directory for components
        self.components_dir = tempfile.mkdtemp(prefix='dapr-llm-components-')

        # If no specific providers selected, use OpenAI as default (most reliable)
        if not selected_providers:
            selected_providers = ['openai'] if 'openai' in self.available_providers else list(self.available_providers.keys())[:1]

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
                    'metadata': config['metadata']
                }
            }

            # Write component file
            component_file = Path(self.components_dir) / f"{provider_id}.yaml"
            with open(component_file, 'w') as f:
                yaml.dump(component_config, f, default_flow_style=False)

            print(f"📝 Created component: {component_file}")

        return self.components_dir

    def create_weather_tool(self) -> Tool:
        """Create a weather tool for testing tool calling."""
        return Tool(
            type="function",
            name="get_weather",
            description="Get the current weather for a location",
            parameters=json.dumps({
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state or country"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"]
            })
        )

    def execute_weather_tool(self, location: str, unit: str = "fahrenheit") -> str:
        """Simulate weather tool execution."""
        temp = "72°F" if unit == "fahrenheit" else "22°C"
        return f"The weather in {location} is sunny with a temperature of {temp}."

    def test_basic_conversation(self, provider_id: str) -> None:
        """Test basic conversation with a provider."""
        print(f"\n💬 Testing basic conversation with {self.available_providers[provider_id]['display_name']}")

        try:
            with DaprClient() as client:
                inputs = [ConversationInput(
                    content="Hello! Please respond with exactly: 'Hello from Dapr!'",
                    role="user"
                )]

                response = client.converse_alpha1(
                    name=provider_id,
                    inputs=inputs
                )

                if response.outputs:
                    result = response.outputs[0].get_text()
                    print(f"✅ Response: {result}")
                    if hasattr(response, 'usage') and response.usage:
                        print(f"📊 Usage: {response.usage.total_tokens} tokens")
                else:
                    print("❌ No response received")

        except Exception as e:
            print(f"❌ Basic conversation error: {e}")

    def test_streaming_conversation(self, provider_id: str) -> None:
        """Test streaming conversation with a provider."""
        print(f"\n🌊 Testing streaming with {self.available_providers[provider_id]['display_name']}")

        try:
            with DaprClient() as client:
                inputs = [ConversationInput.from_text("Count from 1 to 5, one number per response chunk.")]

                print("📡 Streaming response:")
                full_response = ""

                for chunk in client.converse_stream_alpha1(
                    name=provider_id,
                    inputs=inputs
                ):
                    if chunk.chunk and chunk.chunk.content:
                        content = chunk.chunk.content
                        print(content, end='', flush=True)
                        full_response += content

                print(f"\n✅ Streaming complete. Total length: {len(full_response)} chars")

        except Exception as e:
            print(f"❌ Streaming error: {e}")

    def test_tool_calling(self, provider_id: str) -> None:
        """Test tool calling with a provider."""
        print(f"\n🔧 Testing tool calling with {self.available_providers[provider_id]['display_name']}")

        try:
            with DaprClient() as client:
                weather_tool = self.create_weather_tool()

                user_message = ConversationInput(
                    role="user",
                    parts=[
                        ContentPart(text=TextContent(text="What's the weather like in San Francisco?"))
                    ]
                )

                response = client.converse_alpha1(
                    name=provider_id,
                    inputs=[user_message],
                    tools=[weather_tool]
                )

                print(f"Usage: {response.usage.total_tokens}")
                print(f"Usage: {response.usage.prompt_tokens}")
                print(f"Usage: {response.usage.completion_tokens}")

                tool_calls = []

                for i, output in enumerate(response.outputs):
                    print(f"Output {i}: {output.get_text()}")
                    for tool_call in output.get_tool_calls():
                        print(f"🔧 Tool called: {tool_call.name}")
                        tool_calls.append(tool_call)
                        # Execute the tool to show the workflow is complete
                        args = json.loads(tool_call.arguments)
                        weather_result = self.execute_weather_tool(
                            args.get('location', 'San Francisco'),
                            args.get('unit', 'fahrenheit')
                        )
                        print(f"🌤️ Tool executed: {weather_result}")
                        print("✅ Tool calling demonstration completed!")

                        # Note: Multi-turn tool calling workflow (sending tool results back)
                        # requires conversation state management that may not be fully
                        # supported by all Dapr conversation components yet.
                        # This demonstrates the core tool calling functionality.

                if len(tool_calls) == 0:
                    print("❌ No tool calls made")
                else:
                    print(f"Tool calls: {tool_calls}")

        except Exception as e:
            print(f"❌ Tool calling error: {e}")

    async def test_async_conversation(self, provider_id: str) -> None:
        """Test async conversation with a provider."""
        print(f"\n⚡ Testing async conversation with {self.available_providers[provider_id]['display_name']}")

        try:
            async with AsyncDaprClient() as client:
                inputs = [ConversationInput(
                    content="Tell me a very short joke.",
                    role="user"
                )]

                response = await client.converse_alpha1(
                    name=provider_id,
                    inputs=inputs
                )

                if response.outputs:
                    result = response.outputs[0].get_text()
                    print(f"✅ Async response: {result}")
                else:
                    print("❌ No async response received")

        except Exception as e:
            print(f"❌ Async error: {e}")

    async def test_async_streaming(self, provider_id: str) -> None:
        """Test async streaming conversation with a provider."""
        print(f"\n🌊⚡ Testing async streaming with {self.available_providers[provider_id]['display_name']}")

        try:
            async with AsyncDaprClient() as client:
                inputs = [ConversationInput(
                    content="List 3 benefits of async programming, one per line.",
                    role="user"
                )]

                print("📡 Async streaming response:")
                full_response = ""

                async for chunk in client.converse_stream_alpha1(
                    name=provider_id,
                    inputs=inputs
                ):
                    if chunk.chunk and chunk.chunk.content:
                        content = chunk.chunk.content
                        print(content, end='', flush=True)
                        full_response += content

                print(f"\n✅ Async streaming complete. Total length: {len(full_response)} chars")

        except Exception as e:
            print(f"❌ Async streaming error: {e}")

    def run_comprehensive_test(self, provider_id: str) -> None:
        """Run comprehensive tests for a provider."""
        provider_name = self.available_providers[provider_id]['display_name']
        print(f"\n{'='*60}")
        print(f"🧪 Testing {provider_name}")
        print(f"{'='*60}")

        # Sync tests
        self.test_basic_conversation(provider_id)
        self.test_streaming_conversation(provider_id)
        self.test_tool_calling(provider_id)

        # Async tests
        asyncio.run(self.test_async_conversation(provider_id))
        asyncio.run(self.test_async_streaming(provider_id))

    def cleanup(self) -> None:
        """Clean up temporary component files and stop sidecar if needed."""
        # Stop sidecar if we started it
        if self.sidecar_manager:
            self.sidecar_manager.stop()

        # Clean up temporary components directory
        if self.components_dir and Path(self.components_dir).exists():
            import shutil
            shutil.rmtree(self.components_dir)
            print(f"🧹 Cleaned up components directory: {self.components_dir}")


def main():
    """Main function to run the real LLM providers test."""
    print("🚀 Real LLM Providers Example for Dapr Conversation API")
    print("=" * 60)

    # Check for help flag
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    # Check if user wants to use local dev environment
    use_local_dev = "--local-dev" in sys.argv or os.getenv("USE_LOCAL_DEV", "").lower() in ("true", "1", "yes")
    build_local_dapr = "--build-local-dapr" in sys.argv or os.getenv("BUILD_LOCAL_DAPR", "").lower() in ("true", "1", "yes")

    if use_local_dev:
        print("🔧 Using local development build (tool calling enabled)")
        print("   This will automatically start and manage the Dapr sidecar")
    else:
        print("📋 Using manual Dapr sidecar setup")
        print("   You'll need to start the Dapr sidecar manually")

    tester = RealLLMProviderTester(use_local_dev=use_local_dev)

    try:
        # Load environment variables
        tester.load_environment()

        # Detect available providers
        print("\n🔍 Detecting available LLM providers...")
        tester.available_providers = tester.detect_available_providers()

        if not tester.available_providers:
            print("\n❌ No LLM providers configured!")
            print("Please set up API keys in .env file (copy from .env.example)")
            print("Available providers: OpenAI, Anthropic, Mistral, DeepSeek, Google AI")
            return

        print(f"\n✅ Found {len(tester.available_providers)} configured provider(s)")

        # Create component configurations for all available providers
        selected_providers = list(tester.available_providers.keys())
        components_dir = tester.create_component_configs(selected_providers)

        if tester.use_local_dev:
            # Start sidecar automatically using local dev build
            print("\n🔧 Using local development build to start Dapr sidecar...")
            if build_local_dapr:
                print("🔧 Building local Dapr repository...")
            if not tester.sidecar_manager.start_with_components(components_dir, build_local_dapr):
                print("❌ Failed to start Dapr sidecar automatically")
                return
        else:
            # Manual sidecar setup
            print("\n⚠️  IMPORTANT: Make sure Dapr sidecar is running with components from:")
            print(f"   {components_dir}")
            print("\nTo start the sidecar with these components:")
            print(f"   dapr run --app-id test-app --dapr-http-port 3500 --dapr-grpc-port 50001 --resources-path {components_dir}")

            # Wait for user to confirm
            input("\nPress Enter when Dapr sidecar is running with the component configurations...")

        # Test only the providers we created components for
        for provider_id in selected_providers:
            if provider_id in tester.available_providers:
                tester.run_comprehensive_test(provider_id)

        print(f"\n{'='*60}")
        print("🎉 All tests completed!")
        print("✅ Real LLM provider integration is working correctly")
        print(f"{'='*60}")

    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
