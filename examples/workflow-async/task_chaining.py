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

from dapr.ext.workflow import (
    AsyncWorkflowContext,
    DaprWorkflowClient,
    WorkflowActivityContext,
    WorkflowRuntime,
)

wfr = WorkflowRuntime()


@wfr.activity(name='sum')
def sum_act(ctx: WorkflowActivityContext, nums):
    return sum(nums)


@wfr.async_workflow(name='task_chaining_async')
async def orchestrator(ctx: AsyncWorkflowContext):
    a = await ctx.call_activity(sum_act, input=[1, 2])
    b = await ctx.call_activity(sum_act, input=[a, 3])
    c = await ctx.call_activity(sum_act, input=[b, 4])
    return c


def main():
    wfr.start()
    client = DaprWorkflowClient()
    instance_id = 'task_chain_async'
    client.schedule_new_workflow(workflow=orchestrator, instance_id=instance_id)
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
    wfr.shutdown()


if __name__ == '__main__':
    main()
