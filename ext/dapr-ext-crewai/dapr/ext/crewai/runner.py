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

# Runner for executing CrewAI agents as Dapr Workflows.

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from dapr.ext.workflow import DaprWorkflowClient, WorkflowRuntime, WorkflowStatus

from .models import (
    AgentConfig,
    AgentWorkflowInput,
    AgentWorkflowOutput,
    Message,
    MessageRole,
    TaskConfig,
    ToolDefinition,
)
from .workflow import (
    call_llm_activity,
    clear_tool_registry,
    crewai_agent_workflow,
    execute_tool_activity,
    register_tool,
)

if TYPE_CHECKING:
    from crewai import Agent, Task

logger = logging.getLogger(__name__)


class DaprWorkflowAgentRunner:
    """Runner that executes CrewAI agents as Dapr Workflows.

    This runner wraps a CrewAI Agent and executes it using Dapr Workflows,
    making each tool execution a durable activity. This provides:

    - Fault tolerance: Agents automatically resume from the last successful activity
    - Durability: Agent state persists and survives process restarts
    - Observability: Full visibility into agent execution through Dapr's workflow APIs

    Example:
        ```python
        from crewai import Agent, Task
        from crewai.tools import tool
        from dapr.ext.crewai import DaprWorkflowAgentRunner

        @tool("Search the web")
        def search_web(query: str) -> str:
            return f"Results for: {query}"

        # Create your CrewAI agent
        agent = Agent(
            role="Research Assistant",
            goal="Help users find information",
            backstory="An expert researcher",
            tools=[search_web],
            llm="openai/gpt-4o-mini",
        )

        # Define a task
        task = Task(
            description="Research the latest AI developments",
            expected_output="A summary of recent AI news",
            agent=agent,
        )

        # Create runner and start the workflow runtime
        runner = DaprWorkflowAgentRunner(agent=agent)
        runner.start()

        # Run the agent - each tool call is now durable
        async for event in runner.run_async(task=task):
            print(event)

        # Shutdown when done
        runner.shutdown()
        ```

    Attributes:
        agent: The CrewAI Agent to execute
        workflow_runtime: The Dapr WorkflowRuntime instance
        workflow_client: The Dapr WorkflowClient for managing workflows
    """

    def __init__(
        self,
        agent: 'Agent',
        *,
        host: Optional[str] = None,
        port: Optional[str] = None,
        max_iterations: Optional[int] = None,
    ):
        """Initialize the runner.

        Args:
            agent: The CrewAI Agent to execute
            host: Dapr sidecar host (default: localhost)
            port: Dapr sidecar port (default: 50001)
            max_iterations: Maximum number of LLM call iterations
                           (default: uses agent's max_iter)
        """
        self._agent = agent
        self._max_iterations = max_iterations or getattr(agent, 'max_iter', 25)
        self._host = host
        self._port = port

        # Create workflow runtime
        self._workflow_runtime = WorkflowRuntime(host=host, port=port)

        # Register workflow and activities
        self._workflow_runtime.register_workflow(
            crewai_agent_workflow, name='crewai_agent_workflow'
        )
        self._workflow_runtime.register_activity(call_llm_activity, name='call_llm_activity')
        self._workflow_runtime.register_activity(
            execute_tool_activity, name='execute_tool_activity'
        )

        # Register agent's tools in the global registry
        self._register_agent_tools()

        # Create workflow client (for starting/managing workflows)
        self._workflow_client: Optional[DaprWorkflowClient] = None
        self._started = False

    def _register_agent_tools(self) -> None:
        """Register the agent's tools in the global tool registry."""
        clear_tool_registry()

        # Get tools from agent
        tools = getattr(self._agent, 'tools', []) or []

        for tool in tools:
            tool_name = self._get_tool_name(tool)
            tool_def = self._create_tool_definition(tool)
            register_tool(tool_name, tool, tool_def)
            logger.info(f'Registered tool: {tool_name}')

    def _get_tool_name(self, tool: Any) -> str:
        """Get the name of a tool, sanitized for OpenAI API compatibility.

        OpenAI requires tool names to match pattern: ^[a-zA-Z0-9_-]+$
        CrewAI's @tool decorator sets `name` to the description string,
        so we prefer the underlying function name when available.
        """
        import re

        name = None

        # Try to get the underlying function name first (for @tool decorated functions)
        if hasattr(tool, 'func') and hasattr(tool.func, '__name__'):
            name = tool.func.__name__
        elif hasattr(tool, '_run') and hasattr(tool._run, '__name__'):
            # For BaseTool subclasses, try to get a meaningful name
            name = getattr(tool, 'name', None)
        elif hasattr(tool, 'name'):
            name = tool.name
        elif hasattr(tool, '__name__'):
            name = tool.__name__
        else:
            name = str(type(tool).__name__)

        # Sanitize the name to match OpenAI's pattern: ^[a-zA-Z0-9_-]+$
        if name:
            # Replace spaces and invalid chars with underscores
            sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
            # Remove consecutive underscores
            sanitized = re.sub(r'_+', '_', sanitized)
            # Remove leading/trailing underscores
            sanitized = sanitized.strip('_')
            if sanitized:
                return sanitized

        return 'unknown_tool'

    def _create_tool_definition(self, tool: Any) -> ToolDefinition:
        """Create a serializable tool definition from a CrewAI tool."""
        name = self._get_tool_name(tool)

        # Get description - CrewAI @tool decorator stores it in 'description' attribute
        # but also the 'name' attribute might contain the description string
        description = getattr(tool, 'description', '') or ''
        if not description and hasattr(tool, 'name'):
            # If name looks like a description (has spaces), use it as description
            tool_name = getattr(tool, 'name', '')
            if ' ' in tool_name:
                description = tool_name

        # Also try to get docstring from underlying function
        if not description:
            if hasattr(tool, 'func') and tool.func.__doc__:
                description = tool.func.__doc__
            elif hasattr(tool, '_run') and tool._run.__doc__:
                description = tool._run.__doc__

        result_as_answer = getattr(tool, 'result_as_answer', False)

        # Try to extract parameters schema
        parameters = None
        if hasattr(tool, 'args_schema'):
            schema = tool.args_schema
            if hasattr(schema, 'model_json_schema'):
                try:
                    parameters = schema.model_json_schema()
                except Exception:
                    pass
            elif hasattr(schema, 'schema'):
                try:
                    parameters = schema.schema()
                except Exception:
                    pass

        return ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            result_as_answer=result_as_answer,
        )

    def _get_agent_config(self) -> AgentConfig:
        """Extract serializable agent configuration."""
        # Get tools
        tools = getattr(self._agent, 'tools', []) or []
        tool_definitions = []

        for tool in tools:
            tool_definitions.append(self._create_tool_definition(tool))

        # Get model name
        model = 'gpt-4o-mini'  # Default
        if hasattr(self._agent, 'llm'):
            llm = self._agent.llm
            if isinstance(llm, str):
                model = llm
            elif hasattr(llm, 'model_name'):
                model = llm.model_name
            elif hasattr(llm, 'model'):
                model = str(llm.model)

        return AgentConfig(
            role=self._safe_str(self._agent.role) or '',
            goal=self._safe_str(self._agent.goal) or '',
            backstory=self._safe_str(self._agent.backstory) or '',
            model=model,
            tool_definitions=tool_definitions,
            max_iter=self._safe_int(getattr(self._agent, 'max_iter', 25), 25),
            verbose=self._safe_bool(getattr(self._agent, 'verbose', False)),
            allow_delegation=self._safe_bool(getattr(self._agent, 'allow_delegation', False)),
            system_template=self._safe_str(getattr(self._agent, 'system_template', None)),
            prompt_template=self._safe_str(getattr(self._agent, 'prompt_template', None)),
            response_template=self._safe_str(getattr(self._agent, 'response_template', None)),
        )

    def _get_task_config(self, task: 'Task') -> TaskConfig:
        """Extract serializable task configuration."""
        return TaskConfig(
            description=self._safe_str(task.description),
            expected_output=self._safe_str(task.expected_output),
            context=self._safe_str(getattr(task, 'context', None)),
        )

    def _safe_str(self, value: Any) -> Optional[str]:
        """Safely convert a value to string, handling CrewAI's _NotSpecified sentinel.

        CrewAI uses _NotSpecified as a sentinel value for unset optional fields.
        This method converts such values to None for JSON serialization.
        """
        if value is None:
            return None
        # Check for CrewAI's _NotSpecified sentinel
        if type(value).__name__ == '_NotSpecified':
            return None
        if isinstance(value, str):
            return value
        # For other types, convert to string
        return str(value)

    def _safe_int(self, value: Any, default: int) -> int:
        """Safely convert a value to int, handling CrewAI's _NotSpecified sentinel."""
        if value is None or type(value).__name__ == '_NotSpecified':
            return default
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _safe_bool(self, value: Any) -> bool:
        """Safely convert a value to bool, handling CrewAI's _NotSpecified sentinel."""
        if value is None or type(value).__name__ == '_NotSpecified':
            return False
        return bool(value)

    def start(self) -> None:
        """Start the workflow runtime.

        This must be called before running any workflows. It starts listening
        for workflow work items in the background.
        """
        if self._started:
            return

        self._workflow_runtime.start()
        self._workflow_client = DaprWorkflowClient(host=self._host, port=self._port)
        self._started = True
        logger.info('Dapr Workflow runtime started')

    def shutdown(self) -> None:
        """Shutdown the workflow runtime.

        Call this when you're done running workflows to clean up resources.
        """
        if not self._started:
            return

        self._workflow_runtime.shutdown()
        self._started = False
        logger.info('Dapr Workflow runtime stopped')

    async def run_async(
        self,
        task: 'Task',
        *,
        session_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        poll_interval: float = 0.5,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent with a task.

        This starts a new Dapr Workflow for the agent execution. Each tool
        execution becomes a durable activity within the workflow.

        Args:
            task: The CrewAI Task to execute
            session_id: Session ID for the execution
            workflow_id: Optional workflow instance ID (generated if not provided)
            poll_interval: How often to poll for workflow status (seconds)

        Yields:
            Event dictionaries with workflow progress updates

        Raises:
            RuntimeError: If the runner hasn't been started
        """
        if not self._started:
            raise RuntimeError('Runner not started. Call start() first.')

        # Generate session ID if not provided
        if session_id is None:
            session_id = uuid.uuid4().hex[:8]

        # Generate workflow ID if not provided
        if workflow_id is None:
            workflow_id = f'crewai-{session_id}-{uuid.uuid4().hex[:8]}'

        # Create initial user message from task
        messages = [
            Message(
                role=MessageRole.USER,
                content=f'Please complete the following task:\n\n{task.description}\n\nExpected output: {task.expected_output}',
            )
        ]

        # Create workflow input
        workflow_input = AgentWorkflowInput(
            agent_config=self._get_agent_config(),
            task_config=self._get_task_config(task),
            messages=messages,
            session_id=session_id,
            iteration=0,
            max_iterations=self._max_iterations,
        )

        # Convert to dict and verify JSON serializable
        workflow_input_dict = workflow_input.to_dict()
        json.dumps(workflow_input_dict)  # Validate serialization

        # Start the workflow
        logger.info(f'Starting workflow: {workflow_id}')
        self._workflow_client.schedule_new_workflow(
            workflow=crewai_agent_workflow,
            input=workflow_input_dict,
            instance_id=workflow_id,
        )

        # Yield start event
        yield {
            'type': 'workflow_started',
            'workflow_id': workflow_id,
            'session_id': session_id,
            'agent_role': self._agent.role,
        }

        # Poll for workflow completion
        import asyncio

        previous_status = None

        while True:
            await asyncio.sleep(poll_interval)

            state = self._workflow_client.get_workflow_state(instance_id=workflow_id)

            if state is None:
                yield {
                    'type': 'workflow_error',
                    'workflow_id': workflow_id,
                    'error': 'Workflow state not found',
                }
                break

            # Yield status change events
            if state.runtime_status != previous_status:
                yield {
                    'type': 'workflow_status_changed',
                    'workflow_id': workflow_id,
                    'status': str(state.runtime_status),
                    'custom_status': state.serialized_custom_status,
                }
                previous_status = state.runtime_status

            # Check for completion
            if state.runtime_status == WorkflowStatus.COMPLETED:
                output_data = state.serialized_output
                if output_data:
                    try:
                        output_dict = (
                            json.loads(output_data) if isinstance(output_data, str) else output_data
                        )
                        output = AgentWorkflowOutput.from_dict(output_dict)

                        yield {
                            'type': 'workflow_completed',
                            'workflow_id': workflow_id,
                            'final_response': output.final_response,
                            'iterations': output.iterations,
                            'status': output.status,
                        }
                    except Exception as e:
                        yield {
                            'type': 'workflow_completed',
                            'workflow_id': workflow_id,
                            'raw_output': output_data,
                            'parse_error': str(e),
                        }
                else:
                    yield {
                        'type': 'workflow_completed',
                        'workflow_id': workflow_id,
                    }
                break

            elif state.runtime_status == WorkflowStatus.FAILED:
                error_info = None
                if state.failure_details:
                    fd = state.failure_details
                    error_info = {
                        'message': getattr(fd, 'message', str(fd)),
                        'error_type': getattr(fd, 'error_type', None),
                        'stack_trace': getattr(fd, 'stack_trace', None),
                    }
                yield {
                    'type': 'workflow_failed',
                    'workflow_id': workflow_id,
                    'error': error_info,
                }
                break

            elif state.runtime_status == WorkflowStatus.TERMINATED:
                yield {
                    'type': 'workflow_terminated',
                    'workflow_id': workflow_id,
                }
                break

    def run_sync(
        self,
        task: 'Task',
        *,
        session_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        timeout: float = 300.0,
    ) -> AgentWorkflowOutput:
        """Run the agent synchronously and wait for completion.

        This is a convenience method that wraps run_async and waits for
        the workflow to complete.

        Args:
            task: The CrewAI Task to execute
            session_id: Session ID for the execution
            workflow_id: Optional workflow instance ID (generated if not provided)
            timeout: Maximum time to wait for completion (seconds)

        Returns:
            AgentWorkflowOutput with the final result

        Raises:
            RuntimeError: If the runner hasn't been started
            TimeoutError: If the workflow doesn't complete in time
        """
        import asyncio

        async def _run():
            result = None
            async for event in self.run_async(
                task=task,
                session_id=session_id,
                workflow_id=workflow_id,
            ):
                if event['type'] == 'workflow_completed':
                    result = AgentWorkflowOutput(
                        final_response=event.get('final_response'),
                        messages=[],  # Not included in event
                        iterations=event.get('iterations', 0),
                        status=event.get('status', 'completed'),
                    )
                elif event['type'] == 'workflow_failed':
                    error = event.get('error', {})
                    raise RuntimeError(f'Workflow failed: {error.get("message", "Unknown error")}')
                elif event['type'] == 'workflow_error':
                    raise RuntimeError(f'Workflow error: {event.get("error")}')
            return result

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(asyncio.wait_for(_run(), timeout=timeout))
        finally:
            loop.close()

    def get_workflow_status(self, workflow_id: str) -> Optional[dict[str, Any]]:
        """Get the status of a workflow.

        Args:
            workflow_id: The workflow instance ID

        Returns:
            Dictionary with workflow status or None if not found
        """
        if not self._started:
            raise RuntimeError('Runner not started. Call start() first.')

        state = self._workflow_client.get_workflow_state(instance_id=workflow_id)
        if state is None:
            return None

        return {
            'workflow_id': workflow_id,
            'status': str(state.runtime_status),
            'custom_status': state.serialized_custom_status,
            'created_at': str(state.created_at) if state.created_at else None,
            'last_updated_at': str(state.last_updated_at) if state.last_updated_at else None,
        }

    def terminate_workflow(self, workflow_id: str) -> None:
        """Terminate a running workflow.

        Args:
            workflow_id: The workflow instance ID
        """
        if not self._started:
            raise RuntimeError('Runner not started. Call start() first.')

        self._workflow_client.terminate_workflow(instance_id=workflow_id)
        logger.info(f'Terminated workflow: {workflow_id}')

    def purge_workflow(self, workflow_id: str) -> None:
        """Purge a completed or terminated workflow.

        This removes all workflow state from the state store.

        Args:
            workflow_id: The workflow instance ID
        """
        if not self._started:
            raise RuntimeError('Runner not started. Call start() first.')

        self._workflow_client.purge_workflow(instance_id=workflow_id)
        logger.info(f'Purged workflow: {workflow_id}')

    @property
    def agent(self) -> 'Agent':
        """The CrewAI agent being executed."""
        return self._agent

    @property
    def is_running(self) -> bool:
        """Whether the workflow runtime is running."""
        return self._started
