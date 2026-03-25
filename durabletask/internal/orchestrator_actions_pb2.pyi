import datetime

from durabletask.internal import orchestration_pb2 as _orchestration_pb2
from durabletask.internal import history_events_pb2 as _history_events_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ScheduleTaskAction(_message.Message):
    __slots__ = ("name", "version", "input", "router", "taskExecutionId")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    ROUTER_FIELD_NUMBER: _ClassVar[int]
    TASKEXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    router: _orchestration_pb2.TaskRouter
    taskExecutionId: str
    def __init__(self, name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., router: _Optional[_Union[_orchestration_pb2.TaskRouter, _Mapping]] = ..., taskExecutionId: _Optional[str] = ...) -> None: ...

class CreateSubOrchestrationAction(_message.Message):
    __slots__ = ("instanceId", "name", "version", "input", "router")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    ROUTER_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    router: _orchestration_pb2.TaskRouter
    def __init__(self, instanceId: _Optional[str] = ..., name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., router: _Optional[_Union[_orchestration_pb2.TaskRouter, _Mapping]] = ...) -> None: ...

class CreateTimerAction(_message.Message):
    __slots__ = ("fireAt", "name")
    FIREAT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    fireAt: _timestamp_pb2.Timestamp
    name: str
    def __init__(self, fireAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class SendEventAction(_message.Message):
    __slots__ = ("instance", "name", "data")
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    instance: _orchestration_pb2.OrchestrationInstance
    name: str
    data: _wrappers_pb2.StringValue
    def __init__(self, instance: _Optional[_Union[_orchestration_pb2.OrchestrationInstance, _Mapping]] = ..., name: _Optional[str] = ..., data: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class CompleteOrchestrationAction(_message.Message):
    __slots__ = ("orchestrationStatus", "result", "details", "newVersion", "carryoverEvents", "failureDetails")
    ORCHESTRATIONSTATUS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    NEWVERSION_FIELD_NUMBER: _ClassVar[int]
    CARRYOVEREVENTS_FIELD_NUMBER: _ClassVar[int]
    FAILUREDETAILS_FIELD_NUMBER: _ClassVar[int]
    orchestrationStatus: _orchestration_pb2.OrchestrationStatus
    result: _wrappers_pb2.StringValue
    details: _wrappers_pb2.StringValue
    newVersion: _wrappers_pb2.StringValue
    carryoverEvents: _containers.RepeatedCompositeFieldContainer[_history_events_pb2.HistoryEvent]
    failureDetails: _orchestration_pb2.TaskFailureDetails
    def __init__(self, orchestrationStatus: _Optional[_Union[_orchestration_pb2.OrchestrationStatus, str]] = ..., result: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., details: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., newVersion: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., carryoverEvents: _Optional[_Iterable[_Union[_history_events_pb2.HistoryEvent, _Mapping]]] = ..., failureDetails: _Optional[_Union[_orchestration_pb2.TaskFailureDetails, _Mapping]] = ...) -> None: ...

class TerminateOrchestrationAction(_message.Message):
    __slots__ = ("instanceId", "reason", "recurse")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    RECURSE_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    reason: _wrappers_pb2.StringValue
    recurse: bool
    def __init__(self, instanceId: _Optional[str] = ..., reason: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., recurse: bool = ...) -> None: ...

class OrchestratorVersionNotAvailableAction(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class OrchestratorAction(_message.Message):
    __slots__ = ("id", "scheduleTask", "createSubOrchestration", "createTimer", "sendEvent", "completeOrchestration", "terminateOrchestration", "orchestratorVersionNotAvailable", "router")
    ID_FIELD_NUMBER: _ClassVar[int]
    SCHEDULETASK_FIELD_NUMBER: _ClassVar[int]
    CREATESUBORCHESTRATION_FIELD_NUMBER: _ClassVar[int]
    CREATETIMER_FIELD_NUMBER: _ClassVar[int]
    SENDEVENT_FIELD_NUMBER: _ClassVar[int]
    COMPLETEORCHESTRATION_FIELD_NUMBER: _ClassVar[int]
    TERMINATEORCHESTRATION_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATORVERSIONNOTAVAILABLE_FIELD_NUMBER: _ClassVar[int]
    ROUTER_FIELD_NUMBER: _ClassVar[int]
    id: int
    scheduleTask: ScheduleTaskAction
    createSubOrchestration: CreateSubOrchestrationAction
    createTimer: CreateTimerAction
    sendEvent: SendEventAction
    completeOrchestration: CompleteOrchestrationAction
    terminateOrchestration: TerminateOrchestrationAction
    orchestratorVersionNotAvailable: OrchestratorVersionNotAvailableAction
    router: _orchestration_pb2.TaskRouter
    def __init__(self, id: _Optional[int] = ..., scheduleTask: _Optional[_Union[ScheduleTaskAction, _Mapping]] = ..., createSubOrchestration: _Optional[_Union[CreateSubOrchestrationAction, _Mapping]] = ..., createTimer: _Optional[_Union[CreateTimerAction, _Mapping]] = ..., sendEvent: _Optional[_Union[SendEventAction, _Mapping]] = ..., completeOrchestration: _Optional[_Union[CompleteOrchestrationAction, _Mapping]] = ..., terminateOrchestration: _Optional[_Union[TerminateOrchestrationAction, _Mapping]] = ..., orchestratorVersionNotAvailable: _Optional[_Union[OrchestratorVersionNotAvailableAction, _Mapping]] = ..., router: _Optional[_Union[_orchestration_pb2.TaskRouter, _Mapping]] = ...) -> None: ...
