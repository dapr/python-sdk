# -*- coding: utf-8 -*-
# Copyright 2023 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import threading
from dataclasses import asdict, dataclass
from datetime import timedelta
import time

from dapr.clients import DaprClient
import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()


@dataclass
class Order:
    cost: float
    product: str
    quantity: int

    def __str__(self):
        return f'{self.product} ({self.quantity})'


@dataclass
class Approval:
    approver: str

    @staticmethod
    def from_dict(dict):
        return Approval(**dict)


@wfr.workflow(name='purchase_order_wf')
def purchase_order_workflow(ctx: wf.DaprWorkflowContext, order: Order):
    # Orders under $1000 are auto-approved
    if order.cost < 1000:
        return 'Auto-approved'

    # Orders of $1000 or more require manager approval
    yield ctx.call_activity(send_approval_request, input=order)

    # Approvals must be received within 24 hours or they will be canceled.
    approval_event = ctx.wait_for_external_event('approval_received')
    timeout_event = ctx.create_timer(timedelta(hours=24))
    winner = yield wf.when_any([approval_event, timeout_event])
    if winner == timeout_event:
        return 'Cancelled'

    # The order was approved
    yield ctx.call_activity(place_order, input=order)
    approval_details = Approval.from_dict(approval_event.get_result())
    return f"Approved by '{approval_details.approver}'"


@wfr.activity(name='send_approval')
def send_approval_request(_, order: Order) -> None:
    print(f'*** Requesting approval from user for order: {order}')


@wfr.activity
def place_order(_, order: Order) -> None:
    print(f'*** Placing order: {order}')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Order purchasing workflow demo.')
    parser.add_argument('--cost', type=int, default=2000, help='Cost of the order')
    parser.add_argument('--approver', type=str, default='Me', help='Approver name')
    parser.add_argument('--timeout', type=int, default=60, help='Timeout in seconds')
    args = parser.parse_args()

    # start the workflow runtime
    wfr.start()

    # Start a purchase order workflow using the user input
    order = Order(args.cost, 'MyProduct', 1)

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=purchase_order_workflow, input=order)

    def prompt_for_approval():
        # Give the workflow time to start up and notify the user
        time.sleep(2)
        input('Press [ENTER] to approve the order...\n')
        with DaprClient() as d:
            d.raise_workflow_event(
                instance_id=instance_id,
                workflow_component='dapr',
                event_name='approval_received',
                event_data=asdict(Approval(args.approver)),
            )

    # Prompt the user for approval on a background thread
    threading.Thread(target=prompt_for_approval, daemon=True).start()

    # Wait for the orchestration to complete
    try:
        state = wf_client.wait_for_workflow_completion(
            instance_id, timeout_in_seconds=args.timeout + 2
        )
        if not state:
            print('Workflow not found!')  # not expected
        elif state.runtime_status.name == 'COMPLETED':
            print(f'Workflow completed! Result: {state.serialized_output}')
        else:
            print(f'Workflow failed! Status: {state.runtime_status.name}')  # not expected
    except TimeoutError:
        print('*** Workflow timed out!')

    wfr.shutdown()
