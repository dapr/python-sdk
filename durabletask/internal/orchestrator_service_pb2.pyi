import datetime

from durabletask.internal import orchestration_pb2 as _orchestration_pb2
from durabletask.internal import history_events_pb2 as _history_events_pb2
from durabletask.internal import orchestrator_actions_pb2 as _orchestrator_actions_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WorkerCapability(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WORKER_CAPABILITY_UNSPECIFIED: _ClassVar[WorkerCapability]
    WORKER_CAPABILITY_HISTORY_STREAMING: _ClassVar[WorkerCapability]
WORKER_CAPABILITY_UNSPECIFIED: WorkerCapability
WORKER_CAPABILITY_HISTORY_STREAMING: WorkerCapability

class ActivityRequest(_message.Message):
    __slots__ = ("name", "version", "input", "orchestrationInstance", "taskId", "parentTraceContext", "taskExecutionId")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATIONINSTANCE_FIELD_NUMBER: _ClassVar[int]
    TASKID_FIELD_NUMBER: _ClassVar[int]
    PARENTTRACECONTEXT_FIELD_NUMBER: _ClassVar[int]
    TASKEXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    orchestrationInstance: _orchestration_pb2.OrchestrationInstance
    taskId: int
    parentTraceContext: _orchestration_pb2.TraceContext
    taskExecutionId: str
    def __init__(self, name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., orchestrationInstance: _Optional[_Union[_orchestration_pb2.OrchestrationInstance, _Mapping]] = ..., taskId: _Optional[int] = ..., parentTraceContext: _Optional[_Union[_orchestration_pb2.TraceContext, _Mapping]] = ..., taskExecutionId: _Optional[str] = ...) -> None: ...

class ActivityResponse(_message.Message):
    __slots__ = ("instanceId", "taskId", "result", "failureDetails", "completionToken")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    TASKID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    FAILUREDETAILS_FIELD_NUMBER: _ClassVar[int]
    COMPLETIONTOKEN_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    taskId: int
    result: _wrappers_pb2.StringValue
    failureDetails: _orchestration_pb2.TaskFailureDetails
    completionToken: str
    def __init__(self, instanceId: _Optional[str] = ..., taskId: _Optional[int] = ..., result: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., failureDetails: _Optional[_Union[_orchestration_pb2.TaskFailureDetails, _Mapping]] = ..., completionToken: _Optional[str] = ...) -> None: ...

class OrchestratorRequest(_message.Message):
    __slots__ = ("instanceId", "executionId", "pastEvents", "newEvents", "requiresHistoryStreaming", "router")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    PASTEVENTS_FIELD_NUMBER: _ClassVar[int]
    NEWEVENTS_FIELD_NUMBER: _ClassVar[int]
    REQUIRESHISTORYSTREAMING_FIELD_NUMBER: _ClassVar[int]
    ROUTER_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    executionId: _wrappers_pb2.StringValue
    pastEvents: _containers.RepeatedCompositeFieldContainer[_history_events_pb2.HistoryEvent]
    newEvents: _containers.RepeatedCompositeFieldContainer[_history_events_pb2.HistoryEvent]
    requiresHistoryStreaming: bool
    router: _orchestration_pb2.TaskRouter
    def __init__(self, instanceId: _Optional[str] = ..., executionId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., pastEvents: _Optional[_Iterable[_Union[_history_events_pb2.HistoryEvent, _Mapping]]] = ..., newEvents: _Optional[_Iterable[_Union[_history_events_pb2.HistoryEvent, _Mapping]]] = ..., requiresHistoryStreaming: bool = ..., router: _Optional[_Union[_orchestration_pb2.TaskRouter, _Mapping]] = ...) -> None: ...

class OrchestratorResponse(_message.Message):
    __slots__ = ("instanceId", "actions", "customStatus", "completionToken", "numEventsProcessed", "version")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    CUSTOMSTATUS_FIELD_NUMBER: _ClassVar[int]
    COMPLETIONTOKEN_FIELD_NUMBER: _ClassVar[int]
    NUMEVENTSPROCESSED_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    actions: _containers.RepeatedCompositeFieldContainer[_orchestrator_actions_pb2.OrchestratorAction]
    customStatus: _wrappers_pb2.StringValue
    completionToken: str
    numEventsProcessed: _wrappers_pb2.Int32Value
    version: _orchestration_pb2.OrchestrationVersion
    def __init__(self, instanceId: _Optional[str] = ..., actions: _Optional[_Iterable[_Union[_orchestrator_actions_pb2.OrchestratorAction, _Mapping]]] = ..., customStatus: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., completionToken: _Optional[str] = ..., numEventsProcessed: _Optional[_Union[_wrappers_pb2.Int32Value, _Mapping]] = ..., version: _Optional[_Union[_orchestration_pb2.OrchestrationVersion, _Mapping]] = ...) -> None: ...

class CreateInstanceRequest(_message.Message):
    __slots__ = ("instanceId", "name", "version", "input", "scheduledStartTimestamp", "orchestrationIdReusePolicy", "executionId", "tags", "parentTraceContext")
    class TagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEDSTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATIONIDREUSEPOLICY_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    PARENTTRACECONTEXT_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    scheduledStartTimestamp: _timestamp_pb2.Timestamp
    orchestrationIdReusePolicy: _orchestration_pb2.OrchestrationIdReusePolicy
    executionId: _wrappers_pb2.StringValue
    tags: _containers.ScalarMap[str, str]
    parentTraceContext: _orchestration_pb2.TraceContext
    def __init__(self, instanceId: _Optional[str] = ..., name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., scheduledStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., orchestrationIdReusePolicy: _Optional[_Union[_orchestration_pb2.OrchestrationIdReusePolicy, _Mapping]] = ..., executionId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tags: _Optional[_Mapping[str, str]] = ..., parentTraceContext: _Optional[_Union[_orchestration_pb2.TraceContext, _Mapping]] = ...) -> None: ...

class CreateInstanceResponse(_message.Message):
    __slots__ = ("instanceId",)
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    def __init__(self, instanceId: _Optional[str] = ...) -> None: ...

class GetInstanceRequest(_message.Message):
    __slots__ = ("instanceId", "getInputsAndOutputs")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    GETINPUTSANDOUTPUTS_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    getInputsAndOutputs: bool
    def __init__(self, instanceId: _Optional[str] = ..., getInputsAndOutputs: bool = ...) -> None: ...

class GetInstanceResponse(_message.Message):
    __slots__ = ("exists", "orchestrationState")
    EXISTS_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATIONSTATE_FIELD_NUMBER: _ClassVar[int]
    exists: bool
    orchestrationState: _orchestration_pb2.OrchestrationState
    def __init__(self, exists: bool = ..., orchestrationState: _Optional[_Union[_orchestration_pb2.OrchestrationState, _Mapping]] = ...) -> None: ...

class RaiseEventRequest(_message.Message):
    __slots__ = ("instanceId", "name", "input")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    name: str
    input: _wrappers_pb2.StringValue
    def __init__(self, instanceId: _Optional[str] = ..., name: _Optional[str] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class RaiseEventResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TerminateRequest(_message.Message):
    __slots__ = ("instanceId", "output", "recursive")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    RECURSIVE_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    output: _wrappers_pb2.StringValue
    recursive: bool
    def __init__(self, instanceId: _Optional[str] = ..., output: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., recursive: bool = ...) -> None: ...

class TerminateResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SuspendRequest(_message.Message):
    __slots__ = ("instanceId", "reason")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    reason: _wrappers_pb2.StringValue
    def __init__(self, instanceId: _Optional[str] = ..., reason: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class SuspendResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ResumeRequest(_message.Message):
    __slots__ = ("instanceId", "reason")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    reason: _wrappers_pb2.StringValue
    def __init__(self, instanceId: _Optional[str] = ..., reason: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ResumeResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PurgeInstancesRequest(_message.Message):
    __slots__ = ("instanceId", "purgeInstanceFilter", "recursive", "force")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    PURGEINSTANCEFILTER_FIELD_NUMBER: _ClassVar[int]
    RECURSIVE_FIELD_NUMBER: _ClassVar[int]
    FORCE_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    purgeInstanceFilter: PurgeInstanceFilter
    recursive: bool
    force: bool
    def __init__(self, instanceId: _Optional[str] = ..., purgeInstanceFilter: _Optional[_Union[PurgeInstanceFilter, _Mapping]] = ..., recursive: bool = ..., force: bool = ...) -> None: ...

class PurgeInstanceFilter(_message.Message):
    __slots__ = ("createdTimeFrom", "createdTimeTo", "runtimeStatus")
    CREATEDTIMEFROM_FIELD_NUMBER: _ClassVar[int]
    CREATEDTIMETO_FIELD_NUMBER: _ClassVar[int]
    RUNTIMESTATUS_FIELD_NUMBER: _ClassVar[int]
    createdTimeFrom: _timestamp_pb2.Timestamp
    createdTimeTo: _timestamp_pb2.Timestamp
    runtimeStatus: _containers.RepeatedScalarFieldContainer[_orchestration_pb2.OrchestrationStatus]
    def __init__(self, createdTimeFrom: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., createdTimeTo: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., runtimeStatus: _Optional[_Iterable[_Union[_orchestration_pb2.OrchestrationStatus, str]]] = ...) -> None: ...

class PurgeInstancesResponse(_message.Message):
    __slots__ = ("deletedInstanceCount", "isComplete")
    DELETEDINSTANCECOUNT_FIELD_NUMBER: _ClassVar[int]
    ISCOMPLETE_FIELD_NUMBER: _ClassVar[int]
    deletedInstanceCount: int
    isComplete: _wrappers_pb2.BoolValue
    def __init__(self, deletedInstanceCount: _Optional[int] = ..., isComplete: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...

class GetWorkItemsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WorkItem(_message.Message):
    __slots__ = ("orchestratorRequest", "activityRequest", "completionToken")
    ORCHESTRATORREQUEST_FIELD_NUMBER: _ClassVar[int]
    ACTIVITYREQUEST_FIELD_NUMBER: _ClassVar[int]
    COMPLETIONTOKEN_FIELD_NUMBER: _ClassVar[int]
    orchestratorRequest: OrchestratorRequest
    activityRequest: ActivityRequest
    completionToken: str
    def __init__(self, orchestratorRequest: _Optional[_Union[OrchestratorRequest, _Mapping]] = ..., activityRequest: _Optional[_Union[ActivityRequest, _Mapping]] = ..., completionToken: _Optional[str] = ...) -> None: ...

class CompleteTaskResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RerunWorkflowFromEventRequest(_message.Message):
    __slots__ = ("sourceInstanceID", "eventID", "newInstanceID", "input", "overwriteInput", "newChildWorkflowInstanceID")
    SOURCEINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    EVENTID_FIELD_NUMBER: _ClassVar[int]
    NEWINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    OVERWRITEINPUT_FIELD_NUMBER: _ClassVar[int]
    NEWCHILDWORKFLOWINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    sourceInstanceID: str
    eventID: int
    newInstanceID: str
    input: _wrappers_pb2.StringValue
    overwriteInput: bool
    newChildWorkflowInstanceID: str
    def __init__(self, sourceInstanceID: _Optional[str] = ..., eventID: _Optional[int] = ..., newInstanceID: _Optional[str] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., overwriteInput: bool = ..., newChildWorkflowInstanceID: _Optional[str] = ...) -> None: ...

class RerunWorkflowFromEventResponse(_message.Message):
    __slots__ = ("newInstanceID",)
    NEWINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    newInstanceID: str
    def __init__(self, newInstanceID: _Optional[str] = ...) -> None: ...

class ListInstanceIDsRequest(_message.Message):
    __slots__ = ("continuationToken", "pageSize")
    CONTINUATIONTOKEN_FIELD_NUMBER: _ClassVar[int]
    PAGESIZE_FIELD_NUMBER: _ClassVar[int]
    continuationToken: str
    pageSize: int
    def __init__(self, continuationToken: _Optional[str] = ..., pageSize: _Optional[int] = ...) -> None: ...

class ListInstanceIDsResponse(_message.Message):
    __slots__ = ("instanceIds", "continuationToken")
    INSTANCEIDS_FIELD_NUMBER: _ClassVar[int]
    CONTINUATIONTOKEN_FIELD_NUMBER: _ClassVar[int]
    instanceIds: _containers.RepeatedScalarFieldContainer[str]
    continuationToken: str
    def __init__(self, instanceIds: _Optional[_Iterable[str]] = ..., continuationToken: _Optional[str] = ...) -> None: ...

class GetInstanceHistoryRequest(_message.Message):
    __slots__ = ("instanceId",)
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    def __init__(self, instanceId: _Optional[str] = ...) -> None: ...

class GetInstanceHistoryResponse(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[_history_events_pb2.HistoryEvent]
    def __init__(self, events: _Optional[_Iterable[_Union[_history_events_pb2.HistoryEvent, _Mapping]]] = ...) -> None: ...
