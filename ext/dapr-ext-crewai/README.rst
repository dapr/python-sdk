Dapr CrewAI Extension
=====================

This is the Dapr Workflow extension for CrewAI agents.

This extension enables durable execution of CrewAI agents using Dapr Workflows.
Each tool execution in an agent runs as a separate Dapr Workflow activity, providing:

- **Fault tolerance**: Agents automatically resume from the last successful activity on failure
- **Durability**: Agent state is persisted and can survive process restarts
- **Observability**: Full visibility into agent execution through Dapr's workflow APIs

Installation
------------

.. code-block:: bash

    pip install dapr-ext-crewai

Prerequisites
-------------

1. Dapr installed and initialized (``dapr init``)
2. A running Dapr sidecar (``dapr run`` or Kubernetes)

Quick Start
-----------

.. code-block:: python

    from crewai import Agent, Task
    from crewai.tools import tool
    from dapr.ext.crewai import DaprWorkflowAgentRunner

    @tool("Search the web for information")
    def search_web(query: str) -> str:
        """Search the web and return results."""
        return f"Results for: {query}"

    # Create your CrewAI agent
    agent = Agent(
        role="Research Assistant",
        goal="Help users find accurate information",
        backstory="An expert researcher with access to various tools",
        tools=[search_web],
        llm="openai/gpt-4o-mini",
    )

    # Define a task
    task = Task(
        description="Research the latest developments in AI agents",
        expected_output="A comprehensive summary of recent AI agent news",
        agent=agent,
    )

    # Create runner and start the workflow runtime
    runner = DaprWorkflowAgentRunner(agent=agent)
    runner.start()

    # Run the agent - each tool call is now durable
    async for event in runner.run_async(task=task):
        print(event)

    runner.shutdown()

Running with Dapr
-----------------

.. code-block:: bash

    dapr run --app-id crewai-agent --dapr-grpc-port 50001 -- python your_script.py

How It Works
------------

The extension wraps CrewAI agent execution in a Dapr Workflow:

1. **Workflow**: ``crewai_agent_workflow`` orchestrates the agent's execution loop
2. **Activities**:
   - ``call_llm_activity``: Calls the LLM to decide the next action
   - ``execute_tool_activity``: Executes a single tool durably

Each iteration of the agent loop is checkpointed, so if the process fails,
the workflow resumes from the last successful activity.

Advanced Usage
--------------

Synchronous execution:

.. code-block:: python

    result = runner.run_sync(task=task, timeout=300)
    print(result.final_response)

Check workflow status:

.. code-block:: python

    status = runner.get_workflow_status(workflow_id)
    print(status)

Terminate a workflow:

.. code-block:: python

    runner.terminate_workflow(workflow_id)

License
-------

Apache License 2.0
