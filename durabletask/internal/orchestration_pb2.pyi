import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StalledReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PATCH_MISMATCH: _ClassVar[StalledReason]
    VERSION_NOT_AVAILABLE: _ClassVar[StalledReason]

class OrchestrationStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORCHESTRATION_STATUS_RUNNING: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_COMPLETED: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_CONTINUED_AS_NEW: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_FAILED: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_CANCELED: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_TERMINATED: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_PENDING: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_SUSPENDED: _ClassVar[OrchestrationStatus]
    ORCHESTRATION_STATUS_STALLED: _ClassVar[OrchestrationStatus]

class CreateOrchestrationAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR: _ClassVar[CreateOrchestrationAction]
    IGNORE: _ClassVar[CreateOrchestrationAction]
    TERMINATE: _ClassVar[CreateOrchestrationAction]
PATCH_MISMATCH: StalledReason
VERSION_NOT_AVAILABLE: StalledReason
ORCHESTRATION_STATUS_RUNNING: OrchestrationStatus
ORCHESTRATION_STATUS_COMPLETED: OrchestrationStatus
ORCHESTRATION_STATUS_CONTINUED_AS_NEW: OrchestrationStatus
ORCHESTRATION_STATUS_FAILED: OrchestrationStatus
ORCHESTRATION_STATUS_CANCELED: OrchestrationStatus
ORCHESTRATION_STATUS_TERMINATED: OrchestrationStatus
ORCHESTRATION_STATUS_PENDING: OrchestrationStatus
ORCHESTRATION_STATUS_SUSPENDED: OrchestrationStatus
ORCHESTRATION_STATUS_STALLED: OrchestrationStatus
ERROR: CreateOrchestrationAction
IGNORE: CreateOrchestrationAction
TERMINATE: CreateOrchestrationAction

class TaskRouter(_message.Message):
    __slots__ = ("sourceAppID", "targetAppID")
    SOURCEAPPID_FIELD_NUMBER: _ClassVar[int]
    TARGETAPPID_FIELD_NUMBER: _ClassVar[int]
    sourceAppID: str
    targetAppID: str
    def __init__(self, sourceAppID: _Optional[str] = ..., targetAppID: _Optional[str] = ...) -> None: ...

class OrchestrationVersion(_message.Message):
    __slots__ = ("patches", "name")
    PATCHES_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    patches: _containers.RepeatedScalarFieldContainer[str]
    name: str
    def __init__(self, patches: _Optional[_Iterable[str]] = ..., name: _Optional[str] = ...) -> None: ...

class OrchestrationInstance(_message.Message):
    __slots__ = ("instanceId", "executionId")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    executionId: _wrappers_pb2.StringValue
    def __init__(self, instanceId: _Optional[str] = ..., executionId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class TaskFailureDetails(_message.Message):
    __slots__ = ("errorType", "errorMessage", "stackTrace", "innerFailure", "isNonRetriable")
    ERRORTYPE_FIELD_NUMBER: _ClassVar[int]
    ERRORMESSAGE_FIELD_NUMBER: _ClassVar[int]
    STACKTRACE_FIELD_NUMBER: _ClassVar[int]
    INNERFAILURE_FIELD_NUMBER: _ClassVar[int]
    ISNONRETRIABLE_FIELD_NUMBER: _ClassVar[int]
    errorType: str
    errorMessage: str
    stackTrace: _wrappers_pb2.StringValue
    innerFailure: TaskFailureDetails
    isNonRetriable: bool
    def __init__(self, errorType: _Optional[str] = ..., errorMessage: _Optional[str] = ..., stackTrace: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., innerFailure: _Optional[_Union[TaskFailureDetails, _Mapping]] = ..., isNonRetriable: bool = ...) -> None: ...

class ParentInstanceInfo(_message.Message):
    __slots__ = ("taskScheduledId", "name", "version", "orchestrationInstance", "appID")
    TASKSCHEDULEDID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATIONINSTANCE_FIELD_NUMBER: _ClassVar[int]
    APPID_FIELD_NUMBER: _ClassVar[int]
    taskScheduledId: int
    name: _wrappers_pb2.StringValue
    version: _wrappers_pb2.StringValue
    orchestrationInstance: OrchestrationInstance
    appID: str
    def __init__(self, taskScheduledId: _Optional[int] = ..., name: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., orchestrationInstance: _Optional[_Union[OrchestrationInstance, _Mapping]] = ..., appID: _Optional[str] = ...) -> None: ...

class RerunParentInstanceInfo(_message.Message):
    __slots__ = ("instanceID",)
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    instanceID: str
    def __init__(self, instanceID: _Optional[str] = ...) -> None: ...

class TraceContext(_message.Message):
    __slots__ = ("traceParent", "spanID", "traceState")
    TRACEPARENT_FIELD_NUMBER: _ClassVar[int]
    SPANID_FIELD_NUMBER: _ClassVar[int]
    TRACESTATE_FIELD_NUMBER: _ClassVar[int]
    traceParent: str
    spanID: str
    traceState: _wrappers_pb2.StringValue
    def __init__(self, traceParent: _Optional[str] = ..., spanID: _Optional[str] = ..., traceState: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class OrchestrationIdReusePolicy(_message.Message):
    __slots__ = ("operationStatus", "action")
    OPERATIONSTATUS_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    operationStatus: _containers.RepeatedScalarFieldContainer[OrchestrationStatus]
    action: CreateOrchestrationAction
    def __init__(self, operationStatus: _Optional[_Iterable[_Union[OrchestrationStatus, str]]] = ..., action: _Optional[_Union[CreateOrchestrationAction, str]] = ...) -> None: ...

class OrchestrationState(_message.Message):
    __slots__ = ("instanceId", "name", "version", "orchestrationStatus", "scheduledStartTimestamp", "createdTimestamp", "lastUpdatedTimestamp", "input", "output", "customStatus", "failureDetails", "executionId", "completedTimestamp", "parentInstanceId", "tags")
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
    ORCHESTRATIONSTATUS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEDSTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CREATEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LASTUPDATEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    CUSTOMSTATUS_FIELD_NUMBER: _ClassVar[int]
    FAILUREDETAILS_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    COMPLETEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PARENTINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    name: str
    version: _wrappers_pb2.StringValue
    orchestrationStatus: OrchestrationStatus
    scheduledStartTimestamp: _timestamp_pb2.Timestamp
    createdTimestamp: _timestamp_pb2.Timestamp
    lastUpdatedTimestamp: _timestamp_pb2.Timestamp
    input: _wrappers_pb2.StringValue
    output: _wrappers_pb2.StringValue
    customStatus: _wrappers_pb2.StringValue
    failureDetails: TaskFailureDetails
    executionId: _wrappers_pb2.StringValue
    completedTimestamp: _timestamp_pb2.Timestamp
    parentInstanceId: _wrappers_pb2.StringValue
    tags: _containers.ScalarMap[str, str]
    def __init__(self, instanceId: _Optional[str] = ..., name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., orchestrationStatus: _Optional[_Union[OrchestrationStatus, str]] = ..., scheduledStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., createdTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastUpdatedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., output: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., customStatus: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., failureDetails: _Optional[_Union[TaskFailureDetails, _Mapping]] = ..., executionId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., completedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., parentInstanceId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tags: _Optional[_Mapping[str, str]] = ...) -> None: ...
