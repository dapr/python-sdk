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

import dapr.ext.workflow as wf
import time


def main_workflow(ctx: wf.DaprWorkflowContext):
    try:
        instance_id = ctx.instance_id
        child_instance_id = instance_id + '-child'
        print(f'*** Calling child workflow {child_instance_id}')
        yield ctx.call_child_workflow(
            workflow=child_workflow, input=None, instance_id=child_instance_id
        )
    except Exception as e:
        print(f'*** Exception: {e}')

    return


def child_workflow(ctx: wf.DaprWorkflowContext):
    instance_id = ctx.instance_id
    print(f'*** Child workflow {instance_id} called')


if __name__ == '__main__':
    workflowRuntime = wf.WorkflowRuntime('localhost', '50001')
    workflowRuntime.register_workflow(main_workflow)
    workflowRuntime.register_workflow(child_workflow)
    workflowRuntime.start()

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=main_workflow)

    # Wait for the workflow to complete
    time.sleep(5)

    workflowRuntime.shutdown()
