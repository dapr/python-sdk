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

settings = Settings()

counter = 0

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

    workflow_client = DaprWorkflowClient(host, port)
    print("==========Start Counter Increase as per Input:==========")
    _id = workflow_client.schedule_new_workflow(hello_world_wf, input='Hi Counter!')
    # Sleep for a while to let the workflow run
    sleep(1)
    assert counter == 11
    sleep(10)
    workflow_client.raise_workflow_event(_id, "event1")
    # Sleep for a while to let the workflow run
    sleep(1)
    assert counter == 1111
    status = workflow_client.wait_for_workflow_completion(_id, timeout_in_seconds=6000)
    assert status.runtime_status.name == "COMPLETED"
    workflowRuntime.shutdown()

if __name__ == '__main__':
    main()
