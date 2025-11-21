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

from dapr.ext.workflow import AsyncWorkflowContext, WorkflowRuntime


def main():
    rt = WorkflowRuntime()

    @rt.activity(name='add')
    def add(ctx, xy):
        return xy[0] + xy[1]

    @rt.workflow(name='sum_three')
    async def sum_three(ctx: AsyncWorkflowContext, nums):
        a = await ctx.call_activity(add, input=[nums[0], nums[1]])
        b = await ctx.call_activity(add, input=[a, nums[2]])
        return b

    rt.start()
    print("Registered async workflow 'sum_three' and activity 'add'")

    # This example registers only; use Dapr client to start instances externally.


if __name__ == '__main__':
    main()
