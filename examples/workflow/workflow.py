
"""
dapr run python3 workflow.py
"""

# dapr run --app-id wfapp --dapr-grpc-port 4001 --dapr-http-port 3500

from dapr.clients import DaprClient

from time import sleep

with DaprClient() as d:
    instanceId = "pythonInstanceId"
    workflowComponent = "dapr"
    workflowName = "OrderProcessingWorkflow"
    workflowOptions = dict()
    workflowOptions["task_queue"] =  "testQueue"
    inventoryItem = ("Computers", 5, 10)
    item2 = "restock"

    encoded_data = b''.join(bytes(str(element), 'utf-8') for element in inventoryItem)

    # Wait for sidecar to be up within 5 seconds.
    d.wait(5)

    sleep(5)

    # Start the workflow
    start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                     workflow_name=workflowName, input=encoded_data, workflow_options=workflowOptions)
    
    print(f"Attempting to start {workflowName}")

    print(f"start_resp {start_resp.instance_id}")

    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    print(f"Get response from {workflowName} after start call: {getResponse.runtime_status}")

    d.pause_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    print(f"Get response from {workflowName} after pause call: {getResponse.runtime_status}")

    d.resume_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    print(f"Get response from {workflowName} after resume call: {getResponse.runtime_status}")

    d.terminate_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)

    print(f"Get response from {workflowName} after terminate call: {getResponse.runtime_status}")
