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
    WorkflowRuntime,
)

wfr = WorkflowRuntime()


@wfr.async_workflow(name='child_async')
async def child(ctx: AsyncWorkflowContext, n: int) -> int:
    return n * 2


@wfr.async_workflow(name='parent_async')
async def parent(ctx: AsyncWorkflowContext, n: int) -> int:
    r = await ctx.call_child_workflow(child, input=n)
    print(f'Child workflow returned {r}')
    return r + 1


def main():
    wfr.start()
    client = DaprWorkflowClient()
    instance_id = 'parent_async_instance'
    client.schedule_new_workflow(workflow=parent, input=5, instance_id=instance_id)
    client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
    wfr.shutdown()


if __name__ == '__main__':
    main()
