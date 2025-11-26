# -*- coding: utf-8 -*-
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
import asyncio
from datetime import timedelta

from dapr.ext.workflow import (
    DaprWorkflowContext,
    RetryPolicy,
    WorkflowActivityContext,
    WorkflowRuntime,
    when_any,
)
from dapr.ext.workflow.aio import DaprWorkflowClient

from dapr.clients.exceptions import DaprInternalError
from dapr.conf import Settings

settings = Settings()

counter = 0
retry_count = 0
child_orchestrator_count = 0
child_orchestrator_string = ''
child_act_retry_count = 0
instance_id = 'exampleInstanceID'
child_instance_id = 'childInstanceID'
workflow_name = 'hello_world_wf'
child_workflow_name = 'child_wf'
input_data = 'Hi Counter!'
event_name = 'event1'
event_data = 'eventData'
non_existent_id_error = 'no such instance exists'

retry_policy = RetryPolicy(
    first_retry_interval=timedelta(seconds=1),
    max_number_of_attempts=3,
    backoff_coefficient=2,
    max_retry_interval=timedelta(seconds=10),
    retry_timeout=timedelta(seconds=100),
)

wfr = WorkflowRuntime()


@wfr.workflow(name='hello_world_wf')
def hello_world_wf(ctx: DaprWorkflowContext, wf_input):
    print(f'{wf_input}')
    yield ctx.call_activity(hello_act, input=1)
    yield ctx.call_activity(hello_act, input=10)
    yield ctx.call_activity(hello_retryable_act, retry_policy=retry_policy)
    yield ctx.call_child_workflow(child_retryable_wf, retry_policy=retry_policy)

    # Change in event handling: Use when_any to handle both event and timeout
    event = ctx.wait_for_external_event(event_name)
    timeout = ctx.create_timer(timedelta(seconds=30))
    winner = yield when_any([event, timeout])

    if winner == timeout:
        print('Workflow timed out waiting for event')
        return 'Timeout'

    yield ctx.call_activity(hello_act, input=100)
    yield ctx.call_activity(hello_act, input=1000)
    return 'Completed'


@wfr.activity(name='hello_act')
def hello_act(ctx: WorkflowActivityContext, wf_input):
    global counter
    counter += wf_input
    print(f'New counter value is: {counter}!', flush=True)


@wfr.activity(name='hello_retryable_act')
def hello_retryable_act(ctx: WorkflowActivityContext):
    global retry_count
    if (retry_count % 2) == 0:
        print(f'Retry count value is: {retry_count}!', flush=True)
        retry_count += 1
        raise ValueError('Retryable Error')
    print(f'Retry count value is: {retry_count}! This print statement verifies retry', flush=True)
    retry_count += 1


@wfr.workflow(name='child_retryable_wf')
def child_retryable_wf(ctx: DaprWorkflowContext):
    global child_orchestrator_string, child_orchestrator_count
    if not ctx.is_replaying:
        child_orchestrator_count += 1
        print(f'Appending {child_orchestrator_count} to child_orchestrator_string!', flush=True)
        child_orchestrator_string += str(child_orchestrator_count)
    yield ctx.call_activity(
        act_for_child_wf, input=child_orchestrator_count, retry_policy=retry_policy
    )
    if child_orchestrator_count < 3:
        raise ValueError('Retryable Error')


@wfr.activity(name='act_for_child_wf')
def act_for_child_wf(ctx: WorkflowActivityContext, inp):
    global child_orchestrator_string, child_act_retry_count
    inp_char = chr(96 + inp)
    print(f'Appending {inp_char} to child_orchestrator_string!', flush=True)
    child_orchestrator_string += inp_char
    if child_act_retry_count % 2 == 0:
        child_act_retry_count += 1
        raise ValueError('Retryable Error')
    child_act_retry_count += 1


async def main():
    wfr.start()
    wf_client = DaprWorkflowClient()

    try:
        print('==========Start Counter Increase as per Input:==========')
        await wf_client.schedule_new_workflow(
            workflow=hello_world_wf, input=input_data, instance_id=instance_id
        )

        await wf_client.wait_for_workflow_start(instance_id)

        # Sleep to let the workflow run initial activities
        await asyncio.sleep(12)

        assert counter == 11
        assert retry_count == 2
        assert child_orchestrator_string == '1aa2bb3cc'

        # Pause Test
        await wf_client.pause_workflow(instance_id=instance_id)
        metadata = await wf_client.get_workflow_state(instance_id=instance_id)
        print(f'Get response from {workflow_name} after pause call: {metadata.runtime_status.name}')

        # Resume Test
        await wf_client.resume_workflow(instance_id=instance_id)
        metadata = await wf_client.get_workflow_state(instance_id=instance_id)
        print(f'Get response from {workflow_name} after resume call: {metadata.runtime_status.name}')

        await asyncio.sleep(2)  # Give the workflow time to reach the event wait state
        await wf_client.raise_workflow_event(
            instance_id=instance_id, event_name=event_name, data=event_data
        )

        print('========= Waiting for Workflow completion', flush=True)
        try:
            state = await wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
            if state.runtime_status.name == 'COMPLETED':
                print('Workflow completed! Result: {}'.format(state.serialized_output.strip('"')))
            else:
                print(f'Workflow failed! Status: {state.runtime_status.name}')
        except TimeoutError:
            print('*** Workflow timed out!')

        await wf_client.purge_workflow(instance_id=instance_id)
        try:
            await wf_client.get_workflow_state(instance_id=instance_id)
        except DaprInternalError as err:
            if non_existent_id_error in err._message:
                print('Instance Successfully Purged')
    finally:
        wfr.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
