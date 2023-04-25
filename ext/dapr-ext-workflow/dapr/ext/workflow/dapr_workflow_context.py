from typing import Callable, TypeVar, Union
from durabletask import task
from datetime import datetime
from dapr.ext.workflow.workflow_context import WorkflowContext, Workflow

from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class DaprWorkflowContext(WorkflowContext):
    """DaprWorkflowContext that provides proxy access to internal OrchestrationContext instance."""

    __ignore__ = "class mro new init setattr getattr getattribute"

    def __init__(self, obj: task.OrchestrationContext):
        self._obj = obj

    # provide proxy access to regular attributes of wrapped object
    def __getattr__(self, name):
        return getattr(self._obj, name)

    def instance_id(self) -> str:
        return self._obj.instance_id

    def current_utc_datetime(self) -> datetime:
        return self._obj.current_utc_datetime

    def is_replaying(self) -> bool:
        return self._obj.is_replaying

    def create_timer(self, fire_at: datetime) -> task.Task:
        return self._obj.create_timer(fire_at)

    def call_activity(self, activity: Callable[[WorkflowActivityContext, TInput], TOutput], *,
                      input: TInput = None) -> task.Task[TOutput]:
        def act(ctx: task.ActivityContext, inp: TInput):
            daprActContext = WorkflowActivityContext(ctx)
            return activity(daprActContext, inp)
        return self._obj.call_named_activity(name=activity.__name__, activity=act, input=input)

    def call_child_workflow(self, workflow: Workflow, *,
                            input: Union[TInput, None],
                            instance_id: Union[str, None]) -> task.Task[TOutput]:
        def wf(ctx: task.OrchestrationContext, inp: TInput):
            daprWfContext = DaprWorkflowContext(ctx)
            return workflow(daprWfContext, inp)
        return self._obj.call_sub_orchestrator(wf, input=input, instance_id=instance_id)
