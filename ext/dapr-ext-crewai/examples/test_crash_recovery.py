# Copyright 2025 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test script to verify Dapr workflow crash recovery for CrewAI agents.

This test:
1. Creates an agent with a prompt that requires calling 3 tools in sequence
2. Crashes the process during tool 2 execution (after tool 1 completes)
3. On restart, Dapr automatically resumes the workflow and completes it

Usage:
    # Clean up any previous test state first:
    rm -f /tmp/crewai_crash_test_state.json

    # First run (will crash during tool 2):
    dapr run --app-id crewai-crash-test --dapr-grpc-port 50001 -- python test_crash_recovery.py

    # Second run (Dapr auto-resumes and completes):
    dapr run --app-id crewai-crash-test --dapr-grpc-port 50001 -- python test_crash_recovery.py
"""

import asyncio
import json
import os
from pathlib import Path

from crewai import Agent, Task
from crewai.tools import tool
from dapr.ext.crewai import DaprWorkflowAgentRunner
from dapr.ext.workflow import WorkflowStatus


def log(msg: str):
    """Print with immediate flush."""
    print(msg, flush=True)


# State file to track execution across crashes
STATE_FILE = Path('/tmp/crewai_crash_test_state.json')


def load_state() -> dict:
    """Load the test state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'run_count': 0,
        'tool1_executed': False,
        'tool2_executed': False,
        'tool3_executed': False,
        'workflow_scheduled': False,
        'workflow_id': None,  # Store the actual workflow ID
    }


def save_state(state: dict):
    """Save the test state to file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


# Global state for this run
state = load_state()
state['run_count'] += 1
save_state(state)

log(f'\n{"=" * 60}')
log(f'RUN #{state["run_count"]}')
log(f'{"=" * 60}')
log(
    f'Previous state: tool1={state["tool1_executed"]}, '
    f'tool2={state["tool2_executed"]}, tool3={state["tool3_executed"]}'
)
log(f'Workflow previously scheduled: {state["workflow_scheduled"]}')
log(f'Saved workflow_id: {state.get("workflow_id")}')
log(f'{"=" * 60}\n')


@tool('Step one - Initialize data')
def tool_step_one(input_data: str) -> str:
    """Initialize data for the workflow. This is the first step."""
    log(f'\n>>> TOOL 1 EXECUTING: input={input_data}')
    state['tool1_executed'] = True
    save_state(state)
    log('>>> TOOL 1 COMPLETED SUCCESSFULLY')
    return f"Step 1 completed: Initialized with '{input_data}'. Now call step_two___process_data."


@tool('Step two - Process data')
def tool_step_two(data: str) -> str:
    """Process the data from step one. This is the second step."""
    log(f'\n>>> TOOL 2 EXECUTING: data={data}')

    # On first run, crash during tool 2 (after tool 1 completed)
    if state['run_count'] == 1:
        log('>>> TOOL 2: SIMULATING CRASH!')
        log('>>> The process will now terminate...')
        log('>>> Run the program again to test recovery.\n')
        os._exit(1)

    state['tool2_executed'] = True
    save_state(state)
    log('>>> TOOL 2 COMPLETED SUCCESSFULLY')
    return f"Step 2 completed: Processed '{data}'. Now call step_three___finalize_results."


@tool('Step three - Finalize results')
def tool_step_three(processed_data: str) -> str:
    """Finalize and return the results. This is the third and final step."""
    log(f'\n>>> TOOL 3 EXECUTING: processed_data={processed_data}')
    state['tool3_executed'] = True
    save_state(state)
    log('>>> TOOL 3 COMPLETED SUCCESSFULLY')
    return f"Step 3 completed: Final result based on '{processed_data}'. All steps done!"


# Create the agent with all three tools
agent = Agent(
    role='Sequential Task Processor',
    goal='Execute exactly three tools in sequence: step_one, step_two, step_three',
    backstory="""You are a sequential task processor that MUST call tools in a specific order.
    You MUST call all three tools in sequence:
    1. First call 'step_one___initialize_data' with the input
    2. Then call 'step_two___process_data' with the output from step 1
    3. Finally call 'step_three___finalize_results' with the output from step 2

    Do NOT skip any steps. Each tool must be called exactly once in order.""",
    tools=[tool_step_one, tool_step_two, tool_step_three],
    llm='openai/gpt-4o-mini',
    verbose=True,
)

# Create a task that requires all three tools
task = Task(
    description="""Process the input "test_data_123" through all three steps.

    You MUST:
    1. Call step_one___initialize_data with "test_data_123"
    2. Call step_two___process_data with the result from step 1
    3. Call step_three___finalize_results with the result from step 2

    Call each tool exactly once in sequence.""",
    expected_output="""A summary confirming all three steps completed.""",
    agent=agent,
)


async def main():
    """Run the crash recovery test."""

    runner = DaprWorkflowAgentRunner(
        agent=agent,
        max_iterations=10,
    )

    try:
        # Start the runtime - this will auto-resume any in-progress agents
        runner.start()
        log('agent runtime started')
        await asyncio.sleep(1)

        # Only schedule a new run if we haven't already
        if not state['workflow_scheduled']:
            log('Scheduling new workflow...')
            async for event in runner.run_async(task=task):
                event_type = event['type']
                log(f'Event: {event_type}')
                if event_type == 'workflow_started':
                    # Save the actual workflow_id for polling on restart
                    actual_workflow_id = event.get('workflow_id')
                    state['workflow_scheduled'] = True
                    state['workflow_id'] = actual_workflow_id
                    save_state(state)
                    log(f'Workflow started: {actual_workflow_id}')
                elif event_type == 'workflow_status_changed':
                    log(f'Status: {event.get("status")}')
                elif event_type == 'workflow_completed':
                    print_completion(event)
                    break
                elif event_type == 'workflow_failed':
                    log(f'\nWorkflow FAILED: {event.get("error")}')
                    break
        else:
            # Workflow was already scheduled - poll using the saved workflow_id
            saved_workflow_id = state.get('workflow_id')
            log(f'Workflow already scheduled. Polling for completion: {saved_workflow_id}')
            await poll_for_completion(runner, saved_workflow_id)

    except KeyboardInterrupt:
        log('\nInterrupted by user')
    finally:
        runner.shutdown()
        log('Workflow runtime stopped')


async def poll_for_completion(runner: DaprWorkflowAgentRunner, workflow_id: str):
    """Poll an existing workflow until it completes."""
    from dapr.ext.crewai.models import AgentWorkflowOutput

    if not workflow_id:
        log('No workflow_id saved - cannot poll!')
        return

    previous_status = None
    while True:
        await asyncio.sleep(1.0)
        workflow_state = runner._workflow_client.get_workflow_state(instance_id=workflow_id)

        if workflow_state is None:
            log('Workflow state not found!')
            break

        if workflow_state.runtime_status != previous_status:
            log(f'Workflow status: {workflow_state.runtime_status}')
            previous_status = workflow_state.runtime_status

        if workflow_state.runtime_status == WorkflowStatus.COMPLETED:
            output_data = workflow_state.serialized_output
            if output_data:
                output_dict = (
                    json.loads(output_data) if isinstance(output_data, str) else output_data
                )
                output = AgentWorkflowOutput.from_dict(output_dict)
                print_completion(
                    {
                        'final_response': output.final_response,
                        'iterations': output.iterations,
                    }
                )
            break
        elif workflow_state.runtime_status == WorkflowStatus.FAILED:
            log(f'\nWorkflow FAILED: {workflow_state.failure_details}')
            break
        elif workflow_state.runtime_status == WorkflowStatus.TERMINATED:
            log('\nWorkflow was TERMINATED')
            break


def print_completion(event: dict):
    """Print completion summary and verification."""
    log(f'\n{"=" * 60}')
    log('WORKFLOW COMPLETED!')
    log(f'{"=" * 60}')
    log(f'Final Response:\n{event.get("final_response")}')
    log(f'Iterations: {event.get("iterations")}')

    # Reload state to get latest
    final_state = load_state()
    log(f'\n{"=" * 60}')
    log('VERIFICATION:')
    log(f'{"=" * 60}')
    log(f'Tool 1 executed: {final_state["tool1_executed"]}')
    log(f'Tool 2 executed: {final_state["tool2_executed"]}')
    log(f'Tool 3 executed: {final_state["tool3_executed"]}')
    log(f'Total runs: {final_state["run_count"]}')

    if final_state['run_count'] >= 2 and all(
        [
            final_state['tool1_executed'],
            final_state['tool2_executed'],
            final_state['tool3_executed'],
        ]
    ):
        log('\n>>> TEST PASSED: Crash recovery worked!')
        log('>>> Workflow resumed after crash and completed all tools.')


if __name__ == '__main__':
    asyncio.run(main())
