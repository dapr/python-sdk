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

    @rt.async_workflow(name='child')
    async def child(ctx: AsyncWorkflowContext, n):
        return n * 2

    @rt.async_workflow(name='parent')
    async def parent(ctx: AsyncWorkflowContext, n):
        r = await ctx.call_child_workflow(child, input=n)
        return r + 1

    rt.start()
    print("Registered async workflows 'parent' and 'child'")


if __name__ == '__main__':
    main()
