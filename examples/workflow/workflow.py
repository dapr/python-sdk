
"""
dapr run python3 workflow.py
"""

from dapr.clients import DaprClient

with DaprClient() as d:
    workflowName = 'OrderProcessingWorkflow'
    workflowComponent = 'dapr'
    instanceId = 'testInstance'

    inventoryItem = "Computer"
    ammount = "1"

    # Wait for sidecar to be up within 5 seconds.
    d.wait(5)

    # Start the workflow TODO: change the input
    d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                     workflow_name=workflowName, input=None)
    
    print(f"Attempting to start {workflowName}")

    getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent, workflow_name=workflowName)

    print(f"Get response from {workflowName}: {getResponse}")
