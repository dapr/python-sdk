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

import time
from typing import List
import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()


@wfr.workflow(name='batch_processing')
def batch_processing_workflow(ctx: wf.DaprWorkflowContext, wf_input: int):
    # get a batch of N work items to process in parallel
    work_batch = yield ctx.call_activity(get_work_batch, input=wf_input)

    # schedule N parallel tasks to process the work items and wait for all to complete
    parallel_tasks = [
        ctx.call_activity(process_work_item, input=work_item) for work_item in work_batch
    ]
    outputs = yield wf.when_all(parallel_tasks)

    # aggregate the results and send them to another activity
    total = sum(outputs)
    yield ctx.call_activity(process_results, input=total)


@wfr.activity(name='get_batch')
def get_work_batch(ctx, batch_size: int) -> List[int]:
    return [i + 1 for i in range(batch_size)]


@wfr.activity
def process_work_item(ctx, work_item: int) -> int:
    print(f'Processing work item: {work_item}.')
    time.sleep(5)
    result = work_item * 2
    print(f'Work item {work_item} processed. Result: {result}.')
    return result


@wfr.activity(name='final_process')
def process_results(ctx, final_result: int):
    print(f'Final result: {final_result}.')


if __name__ == '__main__':
    wfr.start()
    time.sleep(10)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=batch_processing_workflow, input=10)
    print(f'Workflow started. Instance ID: {instance_id}')
    state = wf_client.wait_for_workflow_completion(instance_id)

    wfr.shutdown()
