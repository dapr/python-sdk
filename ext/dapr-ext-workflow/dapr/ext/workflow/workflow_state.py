from typing import Union
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

    # create proxies for wrapped object's double-underscore attributes
    class __metaclass__(type):
        def __init__(cls, name, bases, dct):

            def make_proxy(name):
                def proxy(self, *args):
                    return getattr(self._obj, name)
                return proxy

            type.__init__(cls, name, bases, dct)
            if cls.__wraps__: # type: ignore
                ignore = set("__%s__" % n for n in cls.__ignore__.split()) # type: ignore
                for name in dir(cls.__wraps__): # type: ignore
                    if name.startswith("__"):
                        if name not in ignore and name not in dct:
                            setattr(cls, name, property(make_proxy(name)))

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