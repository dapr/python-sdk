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
"""Native Pydantic model support in Dapr workflows and activities.

Inputs annotated with a Pydantic BaseModel are reconstructed automatically on
the receiving side — no manual serialization is needed. Outputs are emitted
as plain JSON so the wire format stays interop-friendly with non-Python Dapr
apps.
"""

from time import sleep

from dapr.ext.workflow import (
    DaprWorkflowClient,
    DaprWorkflowContext,
    WorkflowActivityContext,
    WorkflowRuntime,
)
from pydantic import BaseModel


class OrderRequest(BaseModel):
    order_id: str
    customer: str
    amount: float


class OrderResult(BaseModel):
    order_id: str
    approved: bool
    message: str


wfr = WorkflowRuntime()
instance_id = 'pydantic-demo'


@wfr.workflow(name='order_workflow')
def order_workflow(ctx: DaprWorkflowContext, order: OrderRequest):
    # `order` arrives as a real OrderRequest instance — the runtime reads the
    # annotation and reconstructs the model from the decoded JSON automatically.
    if not ctx.is_replaying:
        print(
            f'[workflow] received order {order.order_id} '
            f'for {order.customer} amount={order.amount}',
            flush=True,
        )
    raw = yield ctx.call_activity(approve_order, input=order)
    # Activity results come back as a plain dict. One line turns them into a
    # typed instance.
    result = OrderResult.model_validate(raw)
    if not ctx.is_replaying:
        print(
            f'[workflow] activity returned approved={result.approved}',
            flush=True,
        )
    return result


@wfr.activity(name='approve_order')
def approve_order(ctx: WorkflowActivityContext, order: OrderRequest) -> OrderResult:
    # Same story: `order` is already an OrderRequest instance here.
    print(f'[activity] approving order {order.order_id}', flush=True)
    if order.amount <= 100.0:
        return OrderResult(order_id=order.order_id, approved=True, message='auto-approved')
    return OrderResult(order_id=order.order_id, approved=False, message='needs review')


def main():
    wfr.start()
    sleep(5)
    client = DaprWorkflowClient()

    order = OrderRequest(order_id='O-100', customer='Acme', amount=42.0)
    client.schedule_new_workflow(workflow=order_workflow, input=order, instance_id=instance_id)
    state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)

    # state.serialized_output is a JSON string — reconstruct a typed instance.
    output = OrderResult.model_validate_json(state.serialized_output)
    print(
        f'[client] workflow output: order_id={output.order_id} '
        f'approved={output.approved} message={output.message}',
        flush=True,
    )

    client.purge_workflow(instance_id)
    wfr.shutdown()


if __name__ == '__main__':
    main()
