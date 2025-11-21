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

import time
from datetime import timedelta

from dapr.ext.workflow import (
    AsyncWorkflowContext,
    DaprWorkflowClient,
    WorkflowRuntime,
    WorkflowStatus,
)

wfr = WorkflowRuntime()


@wfr.async_workflow(name='human_approval_async')
async def orchestrator(ctx: AsyncWorkflowContext, request_id: str):
    approve = ctx.wait_for_external_event(f'approve:{request_id}')
    reject = ctx.wait_for_external_event(f'reject:{request_id}')
    decision = await ctx.when_any(
        [
            approve,
            reject,
            ctx.create_timer(timedelta(seconds=5)),
        ]
    )
    if decision == approve:
        print(f'Decision Approved')
        return request_id
    if decision == reject:
        print(f'Decision Rejected')
        return 'REJECTED'
    return 'TIMEOUT'


def main():
    wfr.start()
    client = DaprWorkflowClient()
    instance_id = 'human_approval_async_1'
    try:
        # clean up previous workflow with this ID
        client.terminate_workflow(instance_id)
        client.purge_workflow(instance_id)
    except Exception:
        pass
    client.schedule_new_workflow(workflow=orchestrator, input='req-1', instance_id=instance_id)
    time.sleep(1)
    client.raise_workflow_event(instance_id, 'approve:req-1')
    # In a real scenario, raise approve/reject event from another service.
    wf_state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=20)
    print(f'Workflow state: {wf_state}')

    wfr.shutdown()

    # simple test
    if wf_state.runtime_status != WorkflowStatus.COMPLETED:
        print('Workflow failed with status ', wf_state.runtime_status)
        exit(1)
    if wf_state.serialized_output != '"req-1"':
        print('Workflow result is incorrect!')
        exit(1)


if __name__ == '__main__':
    main()
