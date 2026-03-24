"""End-to-end sample that demonstrates how to configure an orchestrator
that waits for an "approval" event before proceding to the next step. If
the approval isn't received within a specified timeout, the order that is
represented by the orchestration is automatically cancelled."""

import threading
import time
from collections import namedtuple
from dataclasses import dataclass
from datetime import timedelta

from durabletask import client, task, worker


@dataclass
class Order:
    """Represents a purchase order"""

    Cost: float
    Product: str
    Quantity: int

    def __str__(self):
        return f"{self.Product} ({self.Quantity})"


def send_approval_request(_: task.ActivityContext, order: Order) -> None:
    """Activity function that sends an approval request to the manager"""
    time.sleep(5)
    print(f"*** Sending approval request for order: {order}")


def place_order(_: task.ActivityContext, order: Order) -> None:
    """Activity function that places an order"""
    print(f"*** Placing order: {order}")


def purchase_order_workflow(ctx: task.OrchestrationContext, order: Order):
    """Orchestrator function that represents a purchase order workflow"""
    # Orders under $1000 are auto-approved
    if order.Cost < 1000:
        return "Auto-approved"

    # Orders of $1000 or more require manager approval
    yield ctx.call_activity(send_approval_request, input=order)

    # Approvals must be received within 24 hours or they will be canceled.
    approval_event = ctx.wait_for_external_event("approval_received")
    timeout_event = ctx.create_timer(timedelta(hours=24))
    winner = yield task.when_any([approval_event, timeout_event])
    if winner == timeout_event:
        return "Cancelled"

    # The order was approved
    yield ctx.call_activity(place_order, input=order)
    approval_details = approval_event.get_result()
    return f"Approved by '{approval_details.approver}'"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Order purchasing workflow demo.")
    parser.add_argument("--cost", type=int, default=2000, help="Cost of the order")
    parser.add_argument("--approver", type=str, default="Me", help="Approver name")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")
    args = parser.parse_args()

    # configure and start the worker
    with worker.TaskHubGrpcWorker() as w:
        w.add_orchestrator(purchase_order_workflow)
        w.add_activity(send_approval_request)
        w.add_activity(place_order)
        w.start()

        c = client.TaskHubGrpcClient()

        # Start a purchase order workflow using the user input
        order = Order(args.cost, "MyProduct", 1)
        instance_id = c.schedule_new_orchestration(purchase_order_workflow, input=order)

        def prompt_for_approval():
            input("Press [ENTER] to approve the order...\n")
            approval_event = namedtuple("Approval", ["approver"])(args.approver)
            c.raise_orchestration_event(instance_id, "approval_received", data=approval_event)

        # Prompt the user for approval on a background thread
        threading.Thread(target=prompt_for_approval, daemon=True).start()

        # Wait for the orchestration to complete
        try:
            state = c.wait_for_orchestration_completion(instance_id, timeout=args.timeout + 2)
            if not state:
                print("Workflow not found!")  # not expected
            elif state.runtime_status == client.OrchestrationStatus.COMPLETED:
                print(f"Orchestration completed! Result: {state.serialized_output}")
            else:
                state.raise_if_failed()  # raises an exception
        except TimeoutError:
            print("*** Orchestration timed out!")
