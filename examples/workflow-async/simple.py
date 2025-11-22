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
See the specific language governing permissions and
limitations under the License.
"""

import json
from datetime import timedelta
from time import sleep

from dapr.ext.workflow import (
    AsyncWorkflowContext,
    DaprWorkflowClient,
    RetryPolicy,
    WorkflowActivityContext,
    WorkflowRuntime,
    WorkflowStatus,
)

counter = 0
retry_count = 0
child_orchestrator_string = ''
instance_id = 'asyncExampleInstanceID'
child_instance_id = 'asyncChildInstanceID'
workflow_name = 'async_hello_world_wf'
child_workflow_name = 'async_child_wf'
input_data = 'Hi Async Counter!'
event_name = 'event1'
event_data = 'eventData'

retry_policy = RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)

wfr = WorkflowRuntime()


@wfr.async_workflow(name=workflow_name)
async def hello_world_wf(ctx: AsyncWorkflowContext, wf_input):
    # activities
    result_1 = await ctx.call_activity(hello_act, input=1)
    print(f'Activity 1 returned {result_1}')
    result_2 = await ctx.call_activity(hello_act, input=10)
    print(f'Activity 2 returned {result_2}')
    result_3 = await ctx.call_activity(hello_retryable_act, retry_policy=retry_policy)
    print(f'Activity 3 returned {result_3}')
    result_4 = await ctx.call_child_workflow(child_retryable_wf, retry_policy=retry_policy)
    print(f'Child workflow returned {result_4}')

    # Event vs timeout using when_any
    event_1 = ctx.wait_for_external_event(event_name)
    first = await ctx.when_any(
        [
            event_1,
            ctx.create_timer(timedelta(seconds=30)),
        ]
    )

    # Proceed only if event won
    if first == event_1:
        result_5 = await ctx.call_activity(hello_act, input=100)
        result_6 = await ctx.call_activity(hello_act, input=1000)
        return dict(
            result_1=result_1,
            result_2=result_2,
            result_3=result_3,
            result_4=result_4,
            result_5=result_5,
            result_6=result_6,
        )
    return 'Timeout'


@wfr.activity(name='async_hello_act')
def hello_act(ctx: WorkflowActivityContext, wf_input):
    global counter
    counter += wf_input
    return f'Activity returned {wf_input}'


@wfr.activity(name='async_hello_retryable_act')
def hello_retryable_act(ctx: WorkflowActivityContext):
    global retry_count
    if (retry_count % 2) == 0:
        retry_count += 1
        raise ValueError('Retryable Error')
    retry_count += 1
    return f'Activity returned {retry_count}'


@wfr.async_workflow(name=child_workflow_name)
async def child_retryable_wf(ctx: AsyncWorkflowContext):
    # Call activity with retry and simulate retryable workflow failure until certain state
    child_activity_result = await ctx.call_activity(
        act_for_child_wf, input='x', retry_policy=retry_policy
    )
    print(f'Child activity returned {child_activity_result}')
    # In a real sample, you might check state and raise to trigger retry
    return 'ok'


@wfr.activity(name='async_act_for_child_wf')
def act_for_child_wf(ctx: WorkflowActivityContext, inp):
    global child_orchestrator_string
    child_orchestrator_string += inp


def main():
    wf_state = {}
    with wfr:
        wf_client = DaprWorkflowClient()

        wf_client.schedule_new_workflow(
            workflow=hello_world_wf, input=input_data, instance_id=instance_id
        )

        wf_client.wait_for_workflow_start(instance_id)

        # Let initial activities run
        sleep(5)

        # Raise event to continue
        wf_client.raise_workflow_event(
            instance_id=instance_id, event_name=event_name, data={'ok': True}
        )

        # Wait for completion
        wf_state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)

    # simple test
    if wf_state.runtime_status != WorkflowStatus.COMPLETED:
        print('Workflow failed with status ', wf_state.runtime_status)
        exit(1)
    output = json.loads(wf_state.serialized_output)
    if (
        output['result_1'] != 'Activity returned 1'
        or output['result_2'] != 'Activity returned 10'
        or output['result_3'] != 'Activity returned 2'
        or output['result_4'] != 'ok'
        or output['result_5'] != 'Activity returned 100'
        or output['result_6'] != 'Activity returned 1000'
    ):
        print('Workflow result is incorrect!')
        exit(1)


if __name__ == '__main__':
    main()
