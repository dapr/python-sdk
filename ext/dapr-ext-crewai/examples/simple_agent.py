#!/usr/bin/env python3
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

# Example: Simple CrewAI Agent with Dapr Workflows
#
# This example demonstrates how to run a CrewAI agent with durable tool execution
# using Dapr Workflows. Each tool call is executed as a workflow activity,
# providing fault tolerance and durability.
#
# Prerequisites:
#     1. Dapr installed and initialized: dapr init
#     2. Required packages: pip install dapr-ext-crewai crewai
#
# Run with Dapr:
#     dapr run --app-id crewai-agent --dapr-grpc-port 50001 -- python simple_agent.py

import asyncio
import os

from crewai import Agent, Task
from crewai.tools import tool
from dapr.ext.crewai import DaprWorkflowAgentRunner


# Define tools using CrewAI's @tool decorator
@tool('Get the current weather for a city')
def get_weather(city: str) -> str:
    """Get the current weather for a specified city."""
    # In a real application, this would call a weather API
    weather_data = {
        'Tokyo': 'Sunny, 22°C',
        'London': 'Cloudy, 15°C',
        'New York': 'Partly cloudy, 18°C',
        'Paris': 'Rainy, 12°C',
    }
    return weather_data.get(city, f'Weather data not available for {city}')


@tool('Search for information on the web')
def search_web(query: str) -> str:
    """Search the web for information on a given topic."""
    # In a real application, this would call a search API
    return f"Search results for '{query}': Found 10 relevant articles about {query}."


@tool('Get the current date and time')
def get_datetime() -> str:
    """Get the current date and time."""
    from datetime import datetime

    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


async def main():
    # Create a CrewAI agent with tools
    agent = Agent(
        role='Research Assistant',
        goal='Help users find accurate and up-to-date information',
        backstory="""You are an expert research assistant with access to various
        information sources. You excel at finding and synthesizing information
        to provide comprehensive answers to user queries.""",
        tools=[get_weather, search_web, get_datetime],
        llm=os.getenv('CREWAI_LLM', 'openai/gpt-4o-mini'),
        verbose=True,
    )

    # Define a task for the agent
    task = Task(
        description="""Find out the current weather in Tokyo and search for
        recent news about AI developments. Provide a brief summary.""",
        expected_output="""A summary containing:
        1. Current weather in Tokyo
        2. Key recent AI news highlights""",
        agent=agent,
    )

    # Create the Dapr Workflow runner
    runner = DaprWorkflowAgentRunner(
        agent=agent,
        max_iterations=10,
    )

    try:
        # Start the workflow runtime
        print('Starting Dapr Workflow runtime...')
        runner.start()
        print('Runtime started successfully!')

        # Run the agent
        print('\nExecuting agent task...')
        print('=' * 60)

        # Process events as they come
        async for event in runner.run_async(task=task):
            event_type = event['type']

            if event_type == 'workflow_started':
                print(f'\nWorkflow started: {event.get("workflow_id")}')
                print(f'Agent role: {event.get("agent_role")}')

            elif event_type == 'workflow_status_changed':
                print(f'Status: {event.get("status")}')

            elif event_type == 'workflow_completed':
                print('\n' + '=' * 60)
                print('AGENT COMPLETED')
                print('=' * 60)
                print(f'Iterations: {event.get("iterations")}')
                print(f'Status: {event.get("status")}')
                print('\nFinal Response:')
                print('-' * 40)
                print(event.get('final_response', 'No response'))

            elif event_type == 'workflow_failed':
                print(f'\nWorkflow FAILED: {event.get("error")}')

            elif event_type == 'workflow_error':
                print(f'\nWorkflow ERROR: {event.get("error")}')

    except Exception as e:
        print(f'Error: {e}')
        import traceback

        traceback.print_exc()

    finally:
        # Shutdown the runtime
        print('\nShutting down Dapr Workflow runtime...')
        runner.shutdown()
        print('Done!')


if __name__ == '__main__':
    asyncio.run(main())
