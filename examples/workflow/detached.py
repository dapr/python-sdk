# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Detached workflow fan-out example.

The parent workflow spawns one detached workflow per tenant. Detached spawns
are fire-and-forget: the parent receives the spawned instance ID
synchronously and completes without waiting for the detached workflows to
finish. Each detached instance runs independently, with no parent linkage
in its history.

This differs from ``call_child_workflow`` (see child_workflow.py), where the
parent yields a Task and blocks until the child completes.
"""

import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()

TENANTS = ['acme', 'globex', 'initech']


@wfr.workflow
def parent_workflow(ctx: wf.DaprWorkflowContext, tenants: list[str]):
    spawned_ids: list[str] = []
    for tenant in tenants:
        detached_id = f'tenant-{tenant}'
        spawned = ctx.schedule_new_workflow(tenant_workflow, input=tenant, instance_id=detached_id)
        spawned_ids.append(spawned)
        if not ctx.is_replaying:
            print(f'*** Spawned detached workflow {spawned}', flush=True)
    return spawned_ids


@wfr.workflow
def tenant_workflow(ctx: wf.DaprWorkflowContext, tenant: str):
    if not ctx.is_replaying:
        print(f'*** Tenant workflow started for {tenant}', flush=True)
    yield ctx.call_activity(process_tenant, input=tenant)
    return f'{tenant}-done'


@wfr.activity
def process_tenant(ctx: wf.WorkflowActivityContext, tenant: str) -> str:
    print(f'*** Processing tenant {tenant}', flush=True)
    return f'processed:{tenant}'


if __name__ == '__main__':
    wfr.start()

    wf_client = wf.DaprWorkflowClient()
    parent_id = wf_client.schedule_new_workflow(workflow=parent_workflow, input=TENANTS)

    parent_state = wf_client.wait_for_workflow_completion(parent_id, timeout_in_seconds=30)
    print(f'*** Parent workflow {parent_id} finished: {parent_state.runtime_status}', flush=True)

    # The detached workflows continue running independently of the parent.
    # Poll each to confirm they eventually complete.
    for tenant in TENANTS:
        detached_id = f'tenant-{tenant}'
        state = wf_client.wait_for_workflow_completion(detached_id, timeout_in_seconds=30)
        print(
            f'*** Detached workflow {detached_id} finished: '
            f'{state.runtime_status} output={state.serialized_output}',
            flush=True,
        )

    wfr.shutdown()
