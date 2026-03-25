import datetime

from durabletask.internal import orchestration_pb2 as _orchestration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ExecutionStartedEvent(_message.Message):
    __slots__ = ("name", "version", "input", "orchestrationInstance", "parentInstance", "scheduledStartTimestamp", "parentTraceContext", "orchestrationSpanID", "tags")
    class TagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATIONINSTANCE_FIELD_NUMBER: _ClassVar[int]
    PARENTINSTANCE_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEDSTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PARENTTRACECONTEXT_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATIONSPANID_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    orchestrationInstance: _orchestration_pb2.OrchestrationInstance
    parentInstance: _orchestration_pb2.ParentInstanceInfo
    scheduledStartTimestamp: _timestamp_pb2.Timestamp
    parentTraceContext: _orchestration_pb2.TraceContext
    orchestrationSpanID: _wrappers_pb2.StringValue
    tags: _containers.ScalarMap[str, str]
    def __init__(self, name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., orchestrationInstance: _Optional[_Union[_orchestration_pb2.OrchestrationInstance, _Mapping]] = ..., parentInstance: _Optional[_Union[_orchestration_pb2.ParentInstanceInfo, _Mapping]] = ..., scheduledStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., parentTraceContext: _Optional[_Union[_orchestration_pb2.TraceContext, _Mapping]] = ..., orchestrationSpanID: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tags: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ExecutionCompletedEvent(_message.Message):
    __slots__ = ("orchestrationStatus", "result", "failureDetails")
    ORCHESTRATIONSTATUS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    FAILUREDETAILS_FIELD_NUMBER: _ClassVar[int]
    orchestrationStatus: _orchestration_pb2.OrchestrationStatus
    result: _wrappers_pb2.StringValue
    failureDetails: _orchestration_pb2.TaskFailureDetails
    def __init__(self, orchestrationStatus: _Optional[_Union[_orchestration_pb2.OrchestrationStatus, str]] = ..., result: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., failureDetails: _Optional[_Union[_orchestration_pb2.TaskFailureDetails, _Mapping]] = ...) -> None: ...

class ExecutionTerminatedEvent(_message.Message):
    __slots__ = ("input", "recurse")
    INPUT_FIELD_NUMBER: _ClassVar[int]
    RECURSE_FIELD_NUMBER: _ClassVar[int]
    input: _wrappers_pb2.StringValue
    recurse: bool
    def __init__(self, input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., recurse: bool = ...) -> None: ...

class TaskScheduledEvent(_message.Message):
    __slots__ = ("name", "version", "input", "parentTraceContext", "taskExecutionId", "rerunParentInstanceInfo")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    PARENTTRACECONTEXT_FIELD_NUMBER: _ClassVar[int]
    TASKEXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    RERUNPARENTINSTANCEINFO_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    parentTraceContext: _orchestration_pb2.TraceContext
    taskExecutionId: str
    rerunParentInstanceInfo: _orchestration_pb2.RerunParentInstanceInfo
    def __init__(self, name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., parentTraceContext: _Optional[_Union[_orchestration_pb2.TraceContext, _Mapping]] = ..., taskExecutionId: _Optional[str] = ..., rerunParentInstanceInfo: _Optional[_Union[_orchestration_pb2.RerunParentInstanceInfo, _Mapping]] = ...) -> None: ...

class TaskCompletedEvent(_message.Message):
    __slots__ = ("taskScheduledId", "result", "taskExecutionId")
    TASKSCHEDULEDID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    TASKEXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    taskScheduledId: int
    result: _wrappers_pb2.StringValue
    taskExecutionId: str
    def __init__(self, taskScheduledId: _Optional[int] = ..., result: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., taskExecutionId: _Optional[str] = ...) -> None: ...

class TaskFailedEvent(_message.Message):
    __slots__ = ("taskScheduledId", "failureDetails", "taskExecutionId")
    TASKSCHEDULEDID_FIELD_NUMBER: _ClassVar[int]
    FAILUREDETAILS_FIELD_NUMBER: _ClassVar[int]
    TASKEXECUTIONID_FIELD_NUMBER: _ClassVar[int]
    taskScheduledId: int
    failureDetails: _orchestration_pb2.TaskFailureDetails
    taskExecutionId: str
    def __init__(self, taskScheduledId: _Optional[int] = ..., failureDetails: _Optional[_Union[_orchestration_pb2.TaskFailureDetails, _Mapping]] = ..., taskExecutionId: _Optional[str] = ...) -> None: ...

class SubOrchestrationInstanceCreatedEvent(_message.Message):
    __slots__ = ("instanceId", "name", "version", "input", "parentTraceContext", "rerunParentInstanceInfo")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    PARENTTRACECONTEXT_FIELD_NUMBER: _ClassVar[int]
    RERUNPARENTINSTANCEINFO_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    name: str
    version: _wrappers_pb2.StringValue
    input: _wrappers_pb2.StringValue
    parentTraceContext: _orchestration_pb2.TraceContext
    rerunParentInstanceInfo: _orchestration_pb2.RerunParentInstanceInfo
    def __init__(self, instanceId: _Optional[str] = ..., name: _Optional[str] = ..., version: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., parentTraceContext: _Optional[_Union[_orchestration_pb2.TraceContext, _Mapping]] = ..., rerunParentInstanceInfo: _Optional[_Union[_orchestration_pb2.RerunParentInstanceInfo, _Mapping]] = ...) -> None: ...

class SubOrchestrationInstanceCompletedEvent(_message.Message):
    __slots__ = ("taskScheduledId", "result")
    TASKSCHEDULEDID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    taskScheduledId: int
    result: _wrappers_pb2.StringValue
    def __init__(self, taskScheduledId: _Optional[int] = ..., result: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class SubOrchestrationInstanceFailedEvent(_message.Message):
    __slots__ = ("taskScheduledId", "failureDetails")
    TASKSCHEDULEDID_FIELD_NUMBER: _ClassVar[int]
    FAILUREDETAILS_FIELD_NUMBER: _ClassVar[int]
    taskScheduledId: int
    failureDetails: _orchestration_pb2.TaskFailureDetails
    def __init__(self, taskScheduledId: _Optional[int] = ..., failureDetails: _Optional[_Union[_orchestration_pb2.TaskFailureDetails, _Mapping]] = ...) -> None: ...

class TimerCreatedEvent(_message.Message):
    __slots__ = ("fireAt", "name", "rerunParentInstanceInfo")
    FIREAT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    RERUNPARENTINSTANCEINFO_FIELD_NUMBER: _ClassVar[int]
    fireAt: _timestamp_pb2.Timestamp
    name: str
    rerunParentInstanceInfo: _orchestration_pb2.RerunParentInstanceInfo
    def __init__(self, fireAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., name: _Optional[str] = ..., rerunParentInstanceInfo: _Optional[_Union[_orchestration_pb2.RerunParentInstanceInfo, _Mapping]] = ...) -> None: ...

class TimerFiredEvent(_message.Message):
    __slots__ = ("fireAt", "timerId")
    FIREAT_FIELD_NUMBER: _ClassVar[int]
    TIMERID_FIELD_NUMBER: _ClassVar[int]
    fireAt: _timestamp_pb2.Timestamp
    timerId: int
    def __init__(self, fireAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., timerId: _Optional[int] = ...) -> None: ...

class OrchestratorStartedEvent(_message.Message):
    __slots__ = ("version",)
    VERSION_FIELD_NUMBER: _ClassVar[int]
    version: _orchestration_pb2.OrchestrationVersion
    def __init__(self, version: _Optional[_Union[_orchestration_pb2.OrchestrationVersion, _Mapping]] = ...) -> None: ...

class OrchestratorCompletedEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class EventSentEvent(_message.Message):
    __slots__ = ("instanceId", "name", "input")
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    instanceId: str
    name: str
    input: _wrappers_pb2.StringValue
    def __init__(self, instanceId: _Optional[str] = ..., name: _Optional[str] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class EventRaisedEvent(_message.Message):
    __slots__ = ("name", "input")
    NAME_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    name: str
    input: _wrappers_pb2.StringValue
    def __init__(self, name: _Optional[str] = ..., input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ContinueAsNewEvent(_message.Message):
    __slots__ = ("input",)
    INPUT_FIELD_NUMBER: _ClassVar[int]
    input: _wrappers_pb2.StringValue
    def __init__(self, input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ExecutionSuspendedEvent(_message.Message):
    __slots__ = ("input",)
    INPUT_FIELD_NUMBER: _ClassVar[int]
    input: _wrappers_pb2.StringValue
    def __init__(self, input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ExecutionResumedEvent(_message.Message):
    __slots__ = ("input",)
    INPUT_FIELD_NUMBER: _ClassVar[int]
    input: _wrappers_pb2.StringValue
    def __init__(self, input: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class ExecutionStalledEvent(_message.Message):
    __slots__ = ("reason", "description")
    REASON_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    reason: _orchestration_pb2.StalledReason
    description: str
    def __init__(self, reason: _Optional[_Union[_orchestration_pb2.StalledReason, str]] = ..., description: _Optional[str] = ...) -> None: ...

class HistoryEvent(_message.Message):
    __slots__ = ("eventId", "timestamp", "executionStarted", "executionCompleted", "executionTerminated", "taskScheduled", "taskCompleted", "taskFailed", "subOrchestrationInstanceCreated", "subOrchestrationInstanceCompleted", "subOrchestrationInstanceFailed", "timerCreated", "timerFired", "orchestratorStarted", "orchestratorCompleted", "eventSent", "eventRaised", "continueAsNew", "executionSuspended", "executionResumed", "executionStalled", "router")
    EVENTID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONSTARTED_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONTERMINATED_FIELD_NUMBER: _ClassVar[int]
    TASKSCHEDULED_FIELD_NUMBER: _ClassVar[int]
    TASKCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    TASKFAILED_FIELD_NUMBER: _ClassVar[int]
    SUBORCHESTRATIONINSTANCECREATED_FIELD_NUMBER: _ClassVar[int]
    SUBORCHESTRATIONINSTANCECOMPLETED_FIELD_NUMBER: _ClassVar[int]
    SUBORCHESTRATIONINSTANCEFAILED_FIELD_NUMBER: _ClassVar[int]
    TIMERCREATED_FIELD_NUMBER: _ClassVar[int]
    TIMERFIRED_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATORSTARTED_FIELD_NUMBER: _ClassVar[int]
    ORCHESTRATORCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    EVENTSENT_FIELD_NUMBER: _ClassVar[int]
    EVENTRAISED_FIELD_NUMBER: _ClassVar[int]
    CONTINUEASNEW_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONSUSPENDED_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONRESUMED_FIELD_NUMBER: _ClassVar[int]
    EXECUTIONSTALLED_FIELD_NUMBER: _ClassVar[int]
    ROUTER_FIELD_NUMBER: _ClassVar[int]
    eventId: int
    timestamp: _timestamp_pb2.Timestamp
    executionStarted: ExecutionStartedEvent
    executionCompleted: ExecutionCompletedEvent
    executionTerminated: ExecutionTerminatedEvent
    taskScheduled: TaskScheduledEvent
    taskCompleted: TaskCompletedEvent
    taskFailed: TaskFailedEvent
    subOrchestrationInstanceCreated: SubOrchestrationInstanceCreatedEvent
    subOrchestrationInstanceCompleted: SubOrchestrationInstanceCompletedEvent
    subOrchestrationInstanceFailed: SubOrchestrationInstanceFailedEvent
    timerCreated: TimerCreatedEvent
    timerFired: TimerFiredEvent
    orchestratorStarted: OrchestratorStartedEvent
    orchestratorCompleted: OrchestratorCompletedEvent
    eventSent: EventSentEvent
    eventRaised: EventRaisedEvent
    continueAsNew: ContinueAsNewEvent
    executionSuspended: ExecutionSuspendedEvent
    executionResumed: ExecutionResumedEvent
    executionStalled: ExecutionStalledEvent
    router: _orchestration_pb2.TaskRouter
    def __init__(self, eventId: _Optional[int] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., executionStarted: _Optional[_Union[ExecutionStartedEvent, _Mapping]] = ..., executionCompleted: _Optional[_Union[ExecutionCompletedEvent, _Mapping]] = ..., executionTerminated: _Optional[_Union[ExecutionTerminatedEvent, _Mapping]] = ..., taskScheduled: _Optional[_Union[TaskScheduledEvent, _Mapping]] = ..., taskCompleted: _Optional[_Union[TaskCompletedEvent, _Mapping]] = ..., taskFailed: _Optional[_Union[TaskFailedEvent, _Mapping]] = ..., subOrchestrationInstanceCreated: _Optional[_Union[SubOrchestrationInstanceCreatedEvent, _Mapping]] = ..., subOrchestrationInstanceCompleted: _Optional[_Union[SubOrchestrationInstanceCompletedEvent, _Mapping]] = ..., subOrchestrationInstanceFailed: _Optional[_Union[SubOrchestrationInstanceFailedEvent, _Mapping]] = ..., timerCreated: _Optional[_Union[TimerCreatedEvent, _Mapping]] = ..., timerFired: _Optional[_Union[TimerFiredEvent, _Mapping]] = ..., orchestratorStarted: _Optional[_Union[OrchestratorStartedEvent, _Mapping]] = ..., orchestratorCompleted: _Optional[_Union[OrchestratorCompletedEvent, _Mapping]] = ..., eventSent: _Optional[_Union[EventSentEvent, _Mapping]] = ..., eventRaised: _Optional[_Union[EventRaisedEvent, _Mapping]] = ..., continueAsNew: _Optional[_Union[ContinueAsNewEvent, _Mapping]] = ..., executionSuspended: _Optional[_Union[ExecutionSuspendedEvent, _Mapping]] = ..., executionResumed: _Optional[_Union[ExecutionResumedEvent, _Mapping]] = ..., executionStalled: _Optional[_Union[ExecutionStalledEvent, _Mapping]] = ..., router: _Optional[_Union[_orchestration_pb2.TaskRouter, _Mapping]] = ...) -> None: ...
