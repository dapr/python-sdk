from durabletask import client
from enum import Enum


class WorkflowStatus(Enum):
    UNKNOWN = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    TERMINATED = 4
    PENDING = 5
    SUSPENDED = 6


class WorkflowState:
    __ignore__ = "class mro new init setattr getattr getattribute"

    def __init__(self, obj: client.OrchestrationState):
        self._obj = obj

    # provide proxy access to regular attributes of wrapped object
    def __getattr__(self, name):
        return getattr(self._obj, name)

    @property
    def runtime_status(self) -> WorkflowStatus:
        if self._obj.runtime_status == client.OrchestrationStatus.RUNNING:
            return WorkflowStatus.RUNNING
        elif self._obj.runtime_status == client.OrchestrationStatus.COMPLETED:
            return WorkflowStatus.COMPLETED
        elif self._obj.runtime_status == client.OrchestrationStatus.FAILED:
            return WorkflowStatus.FAILED
        elif self._obj.runtime_status == client.OrchestrationStatus.TERMINATED:
            return WorkflowStatus.TERMINATED
        elif self._obj.runtime_status == client.OrchestrationStatus.PENDING:
            return WorkflowStatus.PENDING
        elif self._obj.runtime_status == client.OrchestrationStatus.SUSPENDED:
            return WorkflowStatus.SUSPENDED
        else:
            return WorkflowStatus.UNKNOWN
