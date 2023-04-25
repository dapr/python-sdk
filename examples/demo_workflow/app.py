from dapr.ext.workflow.workflow_runtime_options import WorkflowRuntimeOptions
from dapr.ext.workflow.workflow_client import WorkflowClient
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

def hello_world_wf(ctx: DaprWorkflowContext, input):
    print(f'{input}')
    yield ctx.call_activity(hello_act, input='  Boil one cup of water. ')
    yield ctx.call_activity(hello_act, input='  Add tea leaves to the cup. ')
    yield ctx.call_activity(hello_act, input='  Add boiled water to the cup. ')
    yield ctx.call_activity(hello_act, input='  Add sugar and milk to the cup. ')

def hello_act(ctx: WorkflowActivityContext, input):
    print(f'{input}!', flush=True)

daprOptions = WorkflowRuntimeOptions()
daprOptions.register_workflow(hello_world_wf)
daprOptions.register_activity(hello_act)
daprOptions.run()

client = WorkflowClient("localhost","4001")
print("==========Steps to prepare tea:==========")
id = client.schedule_new_workflow(hello_world_wf, input='Hi Chef!')
status = client.wait_for_workflow_completion(id, timeout=30)
print("  Preparation of tea is ", status.runtime_status.name)
daprOptions.shutdown()