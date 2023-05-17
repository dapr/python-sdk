
"""
dapr run python3 workflow.py
"""

# Running against .NET e2e test
# dapr run python3 workflow.py --dapr-grpc-port 4001 --dapr-http-port 3500 --app-id testapp

from dapr.clients import DaprClient

from time import sleep

from dapr.clients.exceptions import DaprInternalError

with DaprClient() as d:
    instanceId = "exampleInstanceID"
    workflowComponent = "dapr"
    workflowName = "PlaceOrder"
    workflowOptions = dict()
    workflowOptions["task_queue"] =  "testQueue"
    inventoryItem = ("Computers", 5, 10)
    item2 = "paperclips"
    eventName = "ChangePurchaseItem"
    eventData = "eventData"
    nonExistentIDError = "No such instance exists"
    # Wait for sidecar to be up within 5 seconds.
    d.wait(5)

    sleep(5)

    # Start the workflow
    start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                     workflow_name=workflowName, input=item2, workflow_options=workflowOptions)
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
    try:
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    except DaprInternalError as err:
        if nonExistentIDError in err._message:
            print("Instance Successfully Purged")

    # Second test in order to test raise event #

    # Start the workflow
    start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                     workflow_name=workflowName, input=item2, workflow_options=workflowOptions)
    print(f"Attempting to start {workflowName}")
    print(f"start_resp {start_resp.instance_id}")
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    print(f"Get response from {workflowName} after start call: {getResponse.runtime_status}")

    # Raise event
    d.raise_workflow_event(instance_id=instanceId, workflow_component=workflowComponent,
                  event_name=eventName, event_data=eventData)
    
    # Sleep so that the workflow can finish 
    sleep(5)
    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
    outputString = getResponse.properties
    print(f"Output from workflow: {outputString}")