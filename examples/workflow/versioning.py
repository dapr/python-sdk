# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import time
from datetime import timedelta

import dapr.ext.workflow as wf
from durabletask.task import TaskFailedError

wfr = wf.WorkflowRuntime()

current_test = 0
def print_test(message: str):
    print(f'test{current_test}: {message}', flush=True)

def test_full_versioning(client: wf.DaprWorkflowClient):
    global current_test

    # Start with only one version defined. Runnig the workflow should run this version as it normally would.
    current_test = 1
    @wfr.versioned_workflow(name="workflow", is_latest=True)
    def version1_workflow(ctx: wf.DaprWorkflowContext):
        print_test('Received workflow call for version1')
        yield ctx.wait_for_external_event(name='event')
        print_test('Finished workflow for version1')
        return 1

    print_test('triggering workflow')
    instance_id = client.schedule_new_workflow(workflow=version1_workflow)
    client.raise_workflow_event(instance_id, event_name='event')
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)

    # Now we start a workflow, but introduce a latest version half way. It should resume the execution in the old version.
    current_test = 2
    print_test('triggering workflow')
    instance_id = client.schedule_new_workflow(workflow=version1_workflow)
    time.sleep(2) # wait for the workflow to start and wait for the event

    @wfr.versioned_workflow(name="workflow", is_latest=True)
    def version2_workflow(ctx: wf.DaprWorkflowContext):
        print_test('Received workflow call for version2')
        yield ctx.wait_for_external_event(name='event')
        print_test('Finished workflow for version2')
        return 1

    client.raise_workflow_event(instance_id, event_name='event')
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)


    # Now we have the two versions defined, running the workflow now should run v2 as it's the latest version.
    current_test = 3
    print_test('triggering workflow')
    instance_id = client.schedule_new_workflow(workflow=version1_workflow)
    client.raise_workflow_event(instance_id, event_name='event')
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)

def test_patching(client: wf.DaprWorkflowClient):
    global current_test

    @wfr.workflow
    def patching_workflow(ctx: wf.DaprWorkflowContext):
        # This function will be changed throughout the test, to simulate different scenarios
        return workflow_code(ctx)


    # Runs the patched branch by default
    current_test = 4
    def workflow_code(ctx: wf.DaprWorkflowContext):
        print_test('start')
        if ctx.is_patched('patch1'):
            print_test('patch1 is patched')
        else:
            print_test('patch1 is not patched')
        return 1

    instance_id = client.schedule_new_workflow(workflow=patching_workflow)
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)

    # When the execution passed the place where a patch is introduced, it should be not patched.
    def workflow_code(ctx: wf.DaprWorkflowContext):
        print_test('start')
        yield ctx.wait_for_external_event(name='event')
        if ctx.is_patched('patch2'):
            print_test('patch2 is patched')
        else:
            print_test('patch2 is not patched')
        return 1

    current_test = 5
    instance_id = client.schedule_new_workflow(workflow=patching_workflow)
    time.sleep(2)
    def workflow_code(ctx: wf.DaprWorkflowContext):
        print_test('start')
        if ctx.is_patched('patch1'):
            print_test('patch1 is patched')
        else:
            print_test('patch1 is not patched')
        yield ctx.wait_for_external_event(name='event')
        if ctx.is_patched('patch2'):
            print_test('patch2 is patched')
        else:
            print_test('patch2 is not patched')
        return 1

    client.raise_workflow_event(instance_id, event_name='event')
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)

    # It remembers previous patches.
    def workflow_code(ctx: wf.DaprWorkflowContext):
        print_test('start')
        if ctx.is_patched('patch1'):
            pass # keep it silenced for now, we'll add logs later and this ones would confuse the test
        else:
            pass
        yield ctx.wait_for_external_event(name='event')
        if ctx.is_patched('patch2'):
            print_test('patch2 is patched')
        else:
            print_test('patch2 is not patched')
        return 1

    current_test = 6
    instance_id = client.schedule_new_workflow(workflow=patching_workflow)
    time.sleep(2)
    def workflow_code(ctx: wf.DaprWorkflowContext):
        print_test('start')
        if ctx.is_patched('patch1'):
            print_test('patch1 is patched')
        else:
            print_test('patch1 is not patched')
        yield ctx.wait_for_external_event(name='event')
        if ctx.is_patched('patch2'):
            print_test('patch2 is patched')
        else:
            print_test('patch2 is not patched')
        return 1

    client.raise_workflow_event(instance_id, event_name='event')
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)


def test_full_versioning_stall(client: wf.DaprWorkflowClient):
    global current_test

    new_wfr()
    @wfr.versioned_workflow(name="stall_workflow", is_latest=True)
    def version1_workflow(ctx: wf.DaprWorkflowContext):
        print_test('Received workflow call for version1')
        yield ctx.wait_for_external_event(name='event')
        print_test('Finished workflow for version1')
        return 1

    wfr.start()
    current_test = 7
    instance_id = client.schedule_new_workflow(workflow=version1_workflow)
    time.sleep(2)
    new_wfr()

    @wfr.versioned_workflow(name="stall_workflow", is_latest=True)
    def version2_workflow(ctx: wf.DaprWorkflowContext):
        print_test('Received workflow call for version2')
        yield ctx.wait_for_external_event(name='event')
        print_test('Finished workflow for version2')
        return 1
    wfr.start()
    client.raise_workflow_event(instance_id, event_name='event')
    time.sleep(2)
    md = client.get_workflow_state(instance_id)
    if md.runtime_status == wf.WorkflowStatus.STALLED:
        print_test('Workflow is stalled')
    else:
        print_test('Workflow is not stalled')

def test_patching_stall(client: wf.DaprWorkflowClient):
    global current_test

    current_test = 8
    @wfr.workflow
    def patching_workflow(ctx: wf.DaprWorkflowContext):
        # This function will be changed throughout the test, to simulate different scenarios
        return workflow_code(ctx)

    def workflow_code(ctx: wf.DaprWorkflowContext):
        if ctx.is_patched('patch1'):
            pass
        else:
            pass
        yield ctx.wait_for_external_event(name='event')
        return 1

    instance_id = client.schedule_new_workflow(workflow=patching_workflow)
    time.sleep(2)

    def workflow_code(ctx: wf.DaprWorkflowContext):
        # Removed patch1 check
        yield ctx.wait_for_external_event(name='event')
        return 1

    client.raise_workflow_event(instance_id, event_name='event')
    time.sleep(2)
    md = client.get_workflow_state(instance_id)
    if md.runtime_status == wf.WorkflowStatus.STALLED:
        print_test('Workflow is stalled')
    else:
        print_test('Workflow is not stalled')


def new_wfr():
    global wfr
    wfr.shutdown()
    wfr = wf.WorkflowRuntime()


def main():
    args = sys.argv[1:]
    if len(args) == 0:
        print('Usage: python versioning.py <part1|part2>')
        return
    if args[0] == 'part1':
        wfr.start()
        time.sleep(2)  # wait for workflow runtime to start
        client = wf.DaprWorkflowClient()

        test_full_versioning(client)
        test_patching(client)

        test_full_versioning_stall(client)
        test_patching_stall(client)
        wfr.shutdown()
    elif args[0] == 'part2':
        global current_test
        current_test = 100
        print_test('part2')
        @wfr.versioned_workflow(name="stall_workflow", is_latest=False)
        def version1_workflow(ctx: wf.DaprWorkflowContext):
            print_test('Received workflow call for version1')
            yield ctx.wait_for_external_event(name='event')
            print_test('Finished stalled version1 workflow')
            return 1
        @wfr.versioned_workflow(name="stall_workflow", is_latest=True)
        def version2_workflow(ctx: wf.DaprWorkflowContext):
            print_test('Received workflow call for version2')
            yield ctx.wait_for_external_event(name='event')
            print_test('Finished stalled version2 workflow')
            return 1

        @wfr.workflow
        def patching_workflow(ctx: wf.DaprWorkflowContext):
            if ctx.is_patched('patch1'):
                pass
            else:
                pass
            yield ctx.wait_for_external_event(name='event')
            print_test('Finished stalled patching workflow')
            return 1

        wfr.start()
        time.sleep(10)
        wfr.shutdown()

if __name__ == '__main__':
    main()
