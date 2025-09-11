# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Import your main classes here
from dapr.ext.workflow.async_context import AsyncWorkflowContext
from dapr.ext.workflow.dapr_workflow_client import DaprWorkflowClient
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext, when_all, when_any
from dapr.ext.workflow.interceptors import (
    BaseClientInterceptor,
    BaseRuntimeInterceptor,
    BaseWorkflowOutboundInterceptor,
    CallActivityInput,
    CallChildWorkflowInput,
    ClientInterceptor,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    RuntimeInterceptor,
    ScheduleWorkflowInput,
    WorkflowOutboundInterceptor,
    compose_runtime_chain,
    compose_workflow_outbound_chain,
)
from dapr.ext.workflow.retry_policy import RetryPolicy
from dapr.ext.workflow.serializers import (
    ActivityIOAdapter,
    CanonicalSerializable,
    GenericSerializer,
    ensure_canonical_json,
    get_activity_adapter,
    get_serializer,
    register_activity_adapter,
    register_serializer,
    serialize_activity_input,
    serialize_activity_output,
    use_activity_adapter,
)
from dapr.ext.workflow.workflow_activity_context import WorkflowActivityContext
from dapr.ext.workflow.workflow_runtime import WorkflowRuntime, alternate_name
from dapr.ext.workflow.workflow_state import WorkflowState, WorkflowStatus

__all__ = [
    'WorkflowRuntime',
    'DaprWorkflowClient',
    'DaprWorkflowContext',
    'AsyncWorkflowContext',
    'WorkflowActivityContext',
    'WorkflowState',
    'WorkflowStatus',
    'when_all',
    'when_any',
    'alternate_name',
    'RetryPolicy',
    # interceptors
    'ClientInterceptor',
    'BaseClientInterceptor',
    'WorkflowOutboundInterceptor',
    'BaseWorkflowOutboundInterceptor',
    'RuntimeInterceptor',
    'BaseRuntimeInterceptor',
    'ScheduleWorkflowInput',
    'CallChildWorkflowInput',
    'CallActivityInput',
    'ExecuteWorkflowInput',
    'ExecuteActivityInput',
    'compose_workflow_outbound_chain',
    'compose_runtime_chain',
    # serializers
    'CanonicalSerializable',
    'GenericSerializer',
    'ActivityIOAdapter',
    'ensure_canonical_json',
    'register_serializer',
    'get_serializer',
    'register_activity_adapter',
    'get_activity_adapter',
    'use_activity_adapter',
    'serialize_activity_input',
    'serialize_activity_output',
]
