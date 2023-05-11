
"""
dapr run python3 workflow.py
"""

# Running against .NET e2e test
# dapr run python3 workflow.py --dapr-grpc-port 4001 --dapr-http-port 3500 --app-id testapp

from dapr.clients import DaprClient

from dapr.clients.grpc._helpers import to_bytes

from time import sleep

import json

with DaprClient() as d:
    instanceId = "exampleInstanceID"
    workflowComponent = "dapr"
    workflowName = "PlaceOrder"
    workflowOptions = dict()
    workflowOptions["task_queue"] =  "testQueue"
    inventoryItem = ("Computers", 5, 10)
    item2 = "paperclips"

    encoded_data = b''.join(bytes(str(element), 'UTF-8') for element in item2)
    encoded_data2 = json.dumps(item2).encode("UTF-8")

    # Wait for sidecar to be up within 5 seconds.
    d.wait(5)

    sleep(5)

    # Start the workflow
    start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                     workflow_name=workflowName, input=encoded_data2, workflow_options=workflowOptions)
    print(f"Attempting to start {workflowName}")
    print(f"start_resp {start_resp.instance_id}")
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    print(f"Get response from {workflowName} after start call: {getResponse.runtime_status}")

    # Pause Test
    d.pause_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    print(f"Get response from {workflowName} after pause call: {getResponse.runtime_status}")

    # Resume Test
    d.resume_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    print(f"Get response from {workflowName} after resume call: {getResponse.runtime_status}")

    # Terminate Test
    d.terminate_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    print(f"Get response from {workflowName} after terminate call: {getResponse.runtime_status}")

    # Purge Test
    d.purge_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    print(f"Get response from {workflowName} after purge call: {getResponse}")