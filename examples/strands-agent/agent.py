"""
Example demonstrating a Strands Agent with DaprSessionManager for persistent session storage.

This example shows how to:
- Create a Strands Agent with the Strands Agent SDK
- Use DaprSessionManager for distributed session persistence
- Leverage LLM providers through Strands
- Maintain conversation history across restarts
"""

import os
from strands import Agent, tool
from strands.models import OpenAIModel
from dapr.ext.strands import DaprSessionManager
from dapr.clients import DaprClient


@tool
def get_weather(location: str) -> str:
    """Get the current weather for a location.
    
    Args:
        location: The city and state, e.g. "San Francisco, CA"
        
    Returns:
        A description of the current weather
    """
    # Mock implementation for demonstration
    return f"The weather in {location} is sunny and 72°F"


def run_agent_conversation():
    """Run a Strands Agent with Dapr session persistence."""
    
    # Check for OpenAI API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("💡 Set it with: export OPENAI_API_KEY=your-key-here")
        return
    
    session_id = 'assistant-session-1'
    agent_id = 'weather-assistant'
    
    with DaprClient() as dapr_client:
        # Create DaprSessionManager for distributed session storage
        session_manager = DaprSessionManager(
            session_id=session_id,
            state_store_name='statestore',
            dapr_client=dapr_client
        )
        
        # Create a Strands Agent with DaprSessionManager
        agent = Agent(
            # LLM model configuration - API key read from OPENAI_API_KEY env var
            model=OpenAIModel(model_id='gpt-4o'),
            
            # System prompt
            system_prompt=(
                "You are a helpful weather assistant. "
                "You can check the weather for any location. "
                "Be concise and friendly in your responses."
            ),
            
            # Tools available to the agent
            tools=[get_weather],
            
            # Agent metadata
            agent_id=agent_id,
            name='Weather Assistant',
            description='An AI assistant that helps users check the weather',
            
            # State management - custom state dict
            state={
                'role': 'Weather Assistant',
                'goal': 'Help users get weather information',
                'instructions': ['Be concise', 'Be friendly', 'Always use the get_weather tool'],
                'max_iterations': 5,
            },
            
            # Session manager for persistent storage
            # This enables the agent to resume conversations across restarts
            session_manager=session_manager,
        )
        
        # User queries
        queries = [
            "What's the weather in San Francisco?",
            "How about New York?",
        ]
        
        for query in queries:
            print(f"👤 USER: {query}")
            
            try:
                # Run the agent - this will:
                # 1. Add the user message to the conversation
                # 2. Call the LLM to generate a response
                # 3. Execute any tool calls if needed
                # 4. Persist everything through the session manager
                import asyncio
                response = asyncio.run(agent.invoke_async(query))
                
                # Extract the final response text
                if hasattr(response, 'content'):
                    content = response.content
                elif hasattr(response, 'text'):
                    content = response.text
                else:
                    content = str(response)
                    
                print(f"🤖 ASSISTANT: {content}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                print("💡 Tip: Make sure you have OPENAI_API_KEY set in your environment.")
                print("   Or switch to a different model provider (Anthropic, Bedrock, etc.)")
                break
            
            print()
        
        print("✅ Conversation complete!")
        print("🔄 Run again to resume the conversation with full history from Dapr state store.")


if __name__ == '__main__':
    run_agent_conversation()