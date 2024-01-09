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

wfr = wf.WorkflowRuntime()


@wfr.workflow
def main_workflow(ctx: wf.DaprWorkflowContext):
    try:
        instance_id = ctx.instance_id
        child_instance_id = instance_id + '-child'
        print(f'*** Calling child workflow {child_instance_id}', flush=True)
        yield ctx.call_child_workflow(
            workflow=child_workflow, input=None, instance_id=child_instance_id
        )
    except Exception as e:
        print(f'*** Exception: {e}')

    return


@wfr.workflow
def child_workflow(ctx: wf.DaprWorkflowContext):
    instance_id = ctx.instance_id
    print(f'*** Child workflow {instance_id} called', flush=True)


if __name__ == '__main__':
    wfr.start()
    time.sleep(10)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=main_workflow)

    # Wait for the workflow to complete
    time.sleep(5)

    wfr.shutdown()
