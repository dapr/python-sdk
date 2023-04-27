from __future__ import annotations
from datetime import datetime
from typing import Any, TypeVar, Union
from dapr.conf import settings

from durabletask import client
from dapr.ext.workflow.workflow_state import WorkflowState
from dapr.ext.workflow.workflow_context import Workflow

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowClient:

    def __init__(self, host: Union[str, None] = None, port: Union[str, None] = None):
        if host is None:
            host = settings.DAPR_RUNTIME_HOST
        if port is None:
            port = settings.DAPR_GRPC_PORT
        address = f"{host}:{port}"
        self._obj = client.TaskHubGrpcClient(host_address=address)

    def schedule_new_workflow(self, workflow: Workflow, *,
                              input: Union[TInput, None] = None,
                              instance_id: Union[str, None] = None,
                              start_at: Union[datetime, None] = None) -> str:
        return self._obj.schedule_new_orchestration(workflow.__name__,
                                                    input=input, instance_id=instance_id,
                                                    start_at=start_at)

    def get_workflow_state(self, instance_id: str, *,
                           fetch_payloads: bool = True) -> Union[WorkflowState, None]:
        state = self._obj.get_orchestration_state(instance_id, fetch_payloads=fetch_payloads)
        return WorkflowState(state) if state else None

    def wait_for_workflow_start(self, instance_id: str, *,
                                fetch_payloads: bool = False,
                                timeout: int = 60) -> Union[WorkflowState, None]:
        state = self._obj.wait_for_orchestration_start(instance_id,
                                                       fetch_payloads=fetch_payloads,
                                                       timeout=timeout)
        return WorkflowState(state) if state else None

    def wait_for_workflow_completion(self, instance_id: str, *,
                                     fetch_payloads: bool = True,
                                     timeout: int = 60) -> Union[WorkflowState, None]:
        state = self._obj.wait_for_orchestration_completion(instance_id,
                                                            fetch_payloads=fetch_payloads,
                                                            timeout=timeout)
        return WorkflowState(state) if state else None

    def raise_workflow_event(self, instance_id: str, event_name: str, *,
                                  data: Union[Any, None] = None):
        return self._obj.raise_orchestration_event(instance_id, event_name, data=data)
        
    def terminate_workflow(self, instance_id: str, *,
                                output: Union[Any, None] = None):
        return self._obj.terminate_orchestration(instance_id, output=output)

    def pause_workflow(self, instance_id: str):
        return self._obj.suspend_orchestration(instance_id)

    def resume_workflow(self, instance_id: str):
        return self._obj.resume_orchestration(instance_id)
        