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

import asyncio

from dapr.ext.workflow import (
    AsyncWorkflowContext,
    DaprWorkflowClient,
    WorkflowActivityContext,
    WorkflowRuntime,
    WorkflowStatus,
)

# test using sandbox to convert asyncio methods into deterministic ones

wfr = WorkflowRuntime()


@wfr.activity(name='square')
def square(ctx: WorkflowActivityContext, x: int) -> int:
    return x * x


#  workflow function auto-recognize coroutine function and converts this into wfr.async_workflow
@wfr.workflow(name='fan_out_fan_in_async')
async def orchestrator(ctx: AsyncWorkflowContext):
    tasks = [ctx.call_activity(square, input=i) for i in range(1, 6)]
    # 1 + 4 + 9 + 16 + 25 = 55
    results = await asyncio.gather(*tasks)
    total = sum(results)
    return total


def main():
    wfr.start()
    client = DaprWorkflowClient()
    instance_id = 'fofi_async'
    client.schedule_new_workflow(workflow=orchestrator, instance_id=instance_id)
    wf_state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
    print(f'Workflow state: {wf_state}')
    wfr.shutdown()

    # simple test
    if wf_state.runtime_status != WorkflowStatus.COMPLETED:
        print('Workflow failed with status ', wf_state.runtime_status)
        exit(1)
    if wf_state.serialized_output != '55':
        print('Workflow result is incorrect!')
        exit(1)


if __name__ == '__main__':
    main()
