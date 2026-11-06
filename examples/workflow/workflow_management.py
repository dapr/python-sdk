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

"""Workflow management example: list, history and rerun.

An order workflow is scheduled with an amount its charge activity rejects, so
the instance fails. The three management APIs then recover it without touching
the workflow code:

1. ``iter_workflow_instance_ids()`` finds the instance among this app's instance IDs.
2. ``get_workflow_history()`` reads what the instance did and where it stopped.
3. ``rerun_workflow_from_event()`` starts a new instance that replays the
   history up to the failed charge, then re-runs that charge with a corrected
   input.

``validate_order`` had already completed before the target event, so the rerun
replays its recorded result rather than calling it again: it prints once across
both instances. That does not generalise to every activity — an activity still
in flight at the target event is re-dispatched.
"""

import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()

instance_id = 'workflow-management-example'


@wfr.workflow(name='order_workflow')
def order_workflow(ctx: wf.DaprWorkflowContext, amount: int):
    yield ctx.call_activity(validate_order, input=amount)
    receipt = yield ctx.call_activity(charge_order, input=amount)
    return receipt


@wfr.activity(name='validate_order')
def validate_order(ctx: wf.WorkflowActivityContext, amount: int) -> str:
    print(f'*** validate_order: order of {amount} accepted', flush=True)
    return 'valid'


@wfr.activity(name='charge_order')
def charge_order(ctx: wf.WorkflowActivityContext, amount: int) -> str:
    if amount <= 0:
        print(f'*** charge_order: refusing to charge {amount}', flush=True)
        raise ValueError(f'amount must be positive, got {amount}')
    print(f'*** charge_order: charged {amount}', flush=True)
    return f'charged {amount}'


def print_history(client: wf.DaprWorkflowClient, workflow_instance_id: str) -> None:
    for event in client.get_workflow_history(workflow_instance_id):
        rerun_marker = ' [rerunnable]' if event.is_rerunnable else ''
        closes = (
            f' closes=#{event.task_scheduled_id}' if event.task_scheduled_id is not None else ''
        )
        failure = f' error={event.failure_details.message}' if event.failure_details else ''
        print(
            f'*** history: #{event.event_id} {event.event_type.name}'
            f' name={event.name}{closes}{failure}{rerun_marker}',
            flush=True,
        )


def find_charge_event_id(client: wf.DaprWorkflowClient, workflow_instance_id: str) -> int:
    """Finds the event to rerun from: the scheduling of the failed charge."""
    for event in client.get_workflow_history(workflow_instance_id):
        if event.is_rerunnable and event.name == 'charge_order':
            return event.event_id
    raise RuntimeError('no rerunnable charge_order event in history')


def main():
    client = wf.DaprWorkflowClient()
    wfr.start()

    client.schedule_new_workflow(order_workflow, input=0, instance_id=instance_id)
    state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
    print(f'*** first run finished: status={state.runtime_status.name}', flush=True)

    listed = list(client.iter_workflow_instance_ids())
    print(f'*** list: instance present={instance_id in listed}', flush=True)

    print_history(client, instance_id)

    charge_event_id = find_charge_event_id(client, instance_id)
    rerun_instance_id = client.rerun_workflow_from_event(instance_id, charge_event_id, input=25)
    print(
        f'*** rerun started from event #{charge_event_id} '
        f'(the runtime calls this activity task #{charge_event_id})',
        flush=True,
    )

    rerun_state = client.wait_for_workflow_completion(rerun_instance_id, timeout_in_seconds=30)
    print(
        f'*** rerun finished: status={rerun_state.runtime_status.name}'
        f' result={rerun_state.serialized_output}',
        flush=True,
    )

    client.purge_workflow(rerun_instance_id)
    client.purge_workflow(instance_id)
    wfr.shutdown()


if __name__ == '__main__':
    main()
