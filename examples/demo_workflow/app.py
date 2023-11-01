# -*- coding: utf-8 -*-
# Copyright 2023 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from time import sleep
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext, WorkflowActivityContext
from dapr.conf import Settings
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprInternalError

settings = Settings()

counter = 0
instance_id = "exampleInstanceID"
workflow_component = "dapr"
workflow_name = "hello_world_wf"
input_data = "Hi Counter!"
workflow_options = dict()
workflow_options["task_queue"] = "testQueue"
event_name = "event1"
event_data = "eventData"
non_existent_id_error = "no such instance exists"


def hello_world_wf(ctx: DaprWorkflowContext, wf_input):
    print(f'{wf_input}')
    yield ctx.call_activity(hello_act, input=1)
    yield ctx.call_activity(hello_act, input=10)
    yield ctx.wait_for_external_event("event1")
    yield ctx.call_activity(hello_act, input=100)
    yield ctx.call_activity(hello_act, input=1000)


def hello_act(ctx: WorkflowActivityContext, wf_input):
    global counter
    counter += wf_input
    print(f'New counter value is: {counter}!', flush=True)


def main():
    with DaprClient() as d:
        workflow_runtime = WorkflowRuntime()
        workflow_runtime.register_workflow(hello_world_wf)
        workflow_runtime.register_activity(hello_act)
        workflow_runtime.start()

        sleep(2)

        print("==========Start Counter Increase as per Input:==========")
        start_resp = d.start_workflow(instance_id=instance_id,
                                      workflow_component=workflow_component,
                                      workflow_name=workflow_name, input=input_data,
                                      workflow_options=workflow_options)
        print(f"start_resp {start_resp.instance_id}")

        # Sleep for a while to let the workflow run
        sleep(1)
        assert counter == 11

        # Pause Test
        d.pause_workflow(instance_id=instance_id, workflow_component=workflow_component)
        get_response = d.get_workflow(instance_id=instance_id,
                                      workflow_component=workflow_component)
        print(f"Get response from {workflow_name} after pause call: {get_response.runtime_status}")

        # Resume Test
        d.resume_workflow(instance_id=instance_id, workflow_component=workflow_component)
        get_response = d.get_workflow(instance_id=instance_id,
                                      workflow_component=workflow_component)
        print(f"Get response from {workflow_name} after resume call: {get_response.runtime_status}")

        sleep(1)
        # Raise event
        d.raise_workflow_event(instance_id=instance_id, workflow_component=workflow_component,
                               event_name=event_name, event_data=event_data)

        sleep(5)
        # Purge Test
        d.purge_workflow(instance_id=instance_id, workflow_component=workflow_component)
        try:
            d.get_workflow(instance_id=instance_id, workflow_component=workflow_component)
        except DaprInternalError as err:
            if non_existent_id_error in err._message:
                print("Instance Successfully Purged")

        # Kick off another workflow for termination purposes
        # This will also test using the same instance ID on a new workflow after
        # the old instance was purged
        start_resp = d.start_workflow(instance_id=instance_id,
                                      workflow_component=workflow_component,
                                      workflow_name=workflow_name, input=input_data,
                                      workflow_options=workflow_options)
        print(f"start_resp {start_resp.instance_id}")

        # Terminate Test
        d.terminate_workflow(instance_id=instance_id, workflow_component=workflow_component)
        sleep(1)
        get_response = d.get_workflow(instance_id=instance_id,
                                      workflow_component=workflow_component)
        print(f"Get response from {workflow_name} "
              f"after terminate call: {get_response.runtime_status}")

        # Purge Test
        d.purge_workflow(instance_id=instance_id, workflow_component=workflow_component)
        try:
            d.get_workflow(instance_id=instance_id, workflow_component=workflow_component)
        except DaprInternalError as err:
            if non_existent_id_error in err._message:
                print("Instance Successfully Purged")

        workflow_runtime.shutdown()


if __name__ == '__main__':
    main()
