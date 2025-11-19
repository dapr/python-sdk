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

from dapr.ext.workflow import AsyncWorkflowContext, DaprWorkflowClient, WorkflowRuntime

wfr = WorkflowRuntime()


@wfr.async_workflow(name='human_approval_async')
async def orchestrator(ctx: AsyncWorkflowContext, request_id: str):
    decision = await ctx.when_any(
        [
            ctx.wait_for_external_event(f'approve:{request_id}'),
            ctx.wait_for_external_event(f'reject:{request_id}'),
            ctx.create_timer(300.0),
        ]
    )
    if isinstance(decision, dict) and decision.get('approved'):
        return 'APPROVED'
    if isinstance(decision, dict) and decision.get('rejected'):
        return 'REJECTED'
    return 'TIMEOUT'


def main():
    wfr.start()
    client = DaprWorkflowClient()
    instance_id = 'human_approval_async_1'
    client.schedule_new_workflow(workflow=orchestrator, input='REQ-1', instance_id=instance_id)
    # In a real scenario, raise approve/reject event from another service.
    wfr.shutdown()


if __name__ == '__main__':
    main()
