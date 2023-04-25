from typing import TypeVar
from durabletask import worker, task
from dapr.ext.workflow.workflow_context import Workflow
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import Activity, WorkflowActivityContext

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowRuntimeOptions:

    def __init__(self):
        self._worker = worker.TaskHubGrpcWorker()

    def register_workflow(self, fn: Workflow[TInput, TInput]):
        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: TInput):
            """Responsible to call Workflow function in orchestrationWrapper"""
            daprWfContext = DaprWorkflowContext(ctx)
            return fn(daprWfContext, inp)

        self._worker._registry.add_named_orchestrator(fn.__name__, orchestrationWrapper)

    def register_activity(self, fn: Activity):
        def activityWrapper(ctx: task.ActivityContext, inp: TInput):
            """Responsible to call Activity function in activityWrapper"""
            wfActivityContext = WorkflowActivityContext(ctx)
            return fn(wfActivityContext, inp)

        self._worker._registry.add_named_activity(fn.__name__, activityWrapper)

    def run(self):
        self._worker.start()

    def shutdown(self):
        self._worker.stop()
