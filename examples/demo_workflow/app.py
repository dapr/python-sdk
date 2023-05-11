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

from dapr.ext.workflow.workflow_runtime import WorkflowRuntime
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

from dapr.conf import Settings

settings = Settings()

def hello_world_wf(ctx: DaprWorkflowContext, input):
    print(f'{input}')
    yield ctx.call_activity(hello_act, input='  Boil one cup of water. ')
    yield ctx.call_activity(hello_act, input='  Add tea leaves to the cup. ')
    yield ctx.call_activity(hello_act, input='  Add boiled water to the cup. ')
    yield ctx.call_activity(hello_act, input='  Add sugar and milk to the cup. ')

def hello_act(ctx: WorkflowActivityContext, input):
    print(f'{input}!', flush=True)

daprRuntime = WorkflowRuntime()
daprRuntime.register_workflow(hello_world_wf)
daprRuntime.register_activity(hello_act)
daprRuntime.start()

host = settings.DAPR_RUNTIME_HOST
if host is None:
    host = "localhost"
port = settings.DAPR_GRPC_PORT
if port is None:
    port = "4001"

client = DaprWorkflowClient(host, port)
print("==========Steps to prepare tea:==========")
id = client.schedule_new_workflow(hello_world_wf, input='Hi Chef!')
status = client.wait_for_workflow_completion(id, timeout=30)
print("  Preparation of tea is ", status.runtime_status.name)
daprRuntime.shutdown()

