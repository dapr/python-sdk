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

"""History propagation example.

The parent workflow runs a couple of activities, then calls a child workflow
with ``propagation=PropagationScope.OWN_HISTORY`` and an activity with
``propagation=PropagationScope.LINEAGE``. The child workflow and the
downstream activity read the parent's recorded history via
``ctx.get_propagated_history()`` and inspect specific events by name.

This requires a Dapr sidecar built with history propagation enabled
(durabletask-go PR #85 and later). With an older sidecar, the propagation
field is silently dropped and ``get_propagated_history()`` returns ``None``.
"""

from __future__ import annotations

import json

import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()


@wfr.activity(name='validate_merchant')
def validate_merchant(ctx: wf.WorkflowActivityContext, merchant_id: str) -> dict:
    print(f'*** validating merchant {merchant_id}', flush=True)
    return {'merchant_id': merchant_id, 'valid': True}


@wfr.activity(name='log_summary')
def log_summary(ctx: wf.WorkflowActivityContext, _: None) -> str:
    """Activity that reads the parent workflow's propagated history."""
    history = ctx.get_propagated_history()
    if history is None:
        print('*** log_summary: no propagated history (sidecar may not support it)', flush=True)
        return 'no-history'

    workflows = history.get_workflows()
    if not workflows:
        print('*** log_summary: propagated history has no workflows', flush=True)
        return 'empty-history'

    parent = workflows[-1]
    try:
        validate = parent.get_last_activity_by_name('validate_merchant')
    except wf.PropagationNotFoundError:
        print('*** log_summary: parent did not run validate_merchant', flush=True)
        return 'parent-missing-validate'

    print(
        f'*** log_summary saw parent on app {parent.app_id} '
        f'with validate_merchant -> completed={validate.completed} output={validate.output}',
        flush=True,
    )
    return 'logged'


@wfr.workflow(name='process_payment')
def process_payment(ctx: wf.DaprWorkflowContext, _: None):
    """Child workflow: introspect the parent's history before deciding."""
    history = ctx.get_propagated_history()
    if history is None:
        print('*** process_payment: no propagated history', flush=True)
        return 'no-history'

    workflows = history.get_workflows()
    if not workflows:
        print('*** process_payment: propagated history has no workflows', flush=True)
        return 'empty-history'

    parent = workflows[-1]
    try:
        validate = parent.get_last_activity_by_name('validate_merchant')
    except wf.PropagationNotFoundError:
        print('*** process_payment: parent did not run validate_merchant', flush=True)
        return 'parent-missing-validate'

    if not validate.completed:
        print('*** process_payment: parent validate_merchant is not complete yet', flush=True)
        return 'parent-incomplete'

    merchant = json.loads(validate.output or '{}')
    print(
        f'*** process_payment received parent context for merchant {merchant.get("merchant_id")!r}',
        flush=True,
    )
    return 'paid'


@wfr.workflow(name='merchant_checkout')
def merchant_checkout(ctx: wf.DaprWorkflowContext, merchant_id: str):
    """Parent workflow: runs an activity, then propagates its history."""
    yield ctx.call_activity(validate_merchant, input=merchant_id)

    child_result = yield ctx.call_child_workflow(
        process_payment,
        input=None,
        propagation=wf.PropagationScope.OWN_HISTORY,
    )
    print(f'*** child workflow result: {child_result}', flush=True)

    audit = yield ctx.call_activity(
        log_summary,
        input=None,
        propagation=wf.PropagationScope.LINEAGE,
    )
    print(f'*** audit activity result: {audit}', flush=True)
    return {'child': child_result, 'audit': audit}


if __name__ == '__main__':
    wfr.start()

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=merchant_checkout, input='merchant-42')

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    print(
        f'*** workflow completed: status={state.runtime_status.name} output={state.serialized_output}',
        flush=True,
    )

    wfr.shutdown()
