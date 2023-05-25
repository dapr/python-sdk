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
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient, DaprWorkflowContext, WorkflowActivityContext
from dapr.conf import Settings
from dapr.clients import DaprClient
from dapr.clients.exceptions import DaprInternalError

settings = Settings()

counter = 0
instanceId = "exampleInstanceIDs3"
workflowComponent = "dapr"
workflowName = "hello_world_wf"
inputData = "Hi Counter!"
workflowOptions = dict()
workflowOptions["task_queue"] =  "testQueue"
eventName = "event1"
eventData = "eventData"
nonExistentIDError = "No such instance exists"

def hello_world_wf(ctx: DaprWorkflowContext, input):
    print(f'{input}')
    yield ctx.call_activity(hello_act, input=1)
    yield ctx.call_activity(hello_act, input=10)
    yield ctx.wait_for_external_event("event1")
    yield ctx.call_activity(hello_act, input=100)
    yield ctx.call_activity(hello_act, input=1000)

def hello_act(ctx: WorkflowActivityContext, input):
    global counter
    counter += input
    print(f'New counter value is: {counter}!', flush=True)

def main():
    with DaprClient() as d:
        workflowRuntime = WorkflowRuntime()
        workflowRuntime.register_workflow(hello_world_wf)
        workflowRuntime.register_activity(hello_act)
        workflowRuntime.start()

        host = settings.DAPR_RUNTIME_HOST
        if host is None:
            host = "localhost"
        port = settings.DAPR_GRPC_PORT
        if port is None:
            port = "4001"



        print("==========Start Counter Increase as per Input:==========")
        start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                        workflow_name=workflowName, input=inputData, workflow_options=workflowOptions)
        print(f"start_resp {start_resp.instance_id}")

        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after start call: {getResponse.runtime_status}")

        # Sleep for a while to let the workflow run
        sleep(1)
        assert counter == 11

        # Pause Test
        d.pause_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after pause call: {getResponse.runtime_status}")

        # Resume Test
        d.resume_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after resume call: {getResponse.runtime_status}")
        
        sleep(10)
        # Raise event
        d.raise_workflow_event(instance_id=instanceId, workflow_component=workflowComponent,
                    event_name=eventName, event_data=eventData)

        # Terminate Test
        d.terminate_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after terminate call: {getResponse.runtime_status}")

        # Purge Test
        d.purge_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        try:
            getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        except DaprInternalError as err:
            if nonExistentIDError in err._message:
                print("Instance Successfully Purged")
        workflowRuntime.shutdown()

if __name__ == '__main__':
    main()
