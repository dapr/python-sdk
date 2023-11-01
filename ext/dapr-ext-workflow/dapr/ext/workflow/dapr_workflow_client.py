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

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional, TypeVar

from durabletask import client

from dapr.ext.workflow.workflow_state import WorkflowState
from dapr.ext.workflow.workflow_context import Workflow
from dapr.ext.workflow.util import getAddress

from dapr.clients import DaprInternalError
from dapr.clients.http.client import DAPR_API_TOKEN_HEADER
from dapr.conf import settings
from dapr.conf.helpers import GrpcEndpoint

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class DaprWorkflowClient:
    """Defines client operations for managing Dapr Workflow instances.

       This is an alternative to the general purpose Dapr client. It uses a gRPC connection to send
       commands directly to the workflow engine, bypassing the Dapr API layer.

       This client is intended to be used by workflow application, not by general purpose
       application.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[str] = None):
        address = getAddress(host, port)

        try:
            uri = GrpcEndpoint(address)
        except ValueError as error:
            raise DaprInternalError(f'{error}') from error

        metadata = tuple()
        if settings.DAPR_API_TOKEN:
            metadata = ((DAPR_API_TOKEN_HEADER, settings.DAPR_API_TOKEN),)
        self.__obj = client.TaskHubGrpcClient(host_address=uri.endpoint, metadata=metadata,
                                              secure_channel=uri.tls)

    def schedule_new_workflow(self, workflow: Workflow, *, input: Optional[TInput] = None,
                              instance_id: Optional[str] = None,
                              start_at: Optional[datetime] = None) -> str:
        """Schedules a new workflow instance for execution.

        Args:
            workflow: The workflow to schedule.
            input: The optional input to pass to the scheduled workflow instance. This must be a
            serializable value.
            instance_id: The unique ID of the workflow instance to schedule. If not specified, a
            new GUID value is used.
            start_at: The time when the workflow instance should start executing.
            If not specified or if a date-time in the past is specified, the workflow instance will
            be scheduled immediately.

        Returns:
            The ID of the scheduled workflow instance.
        """
        return self.__obj.schedule_new_orchestration(workflow.__name__, input=input,
                                                     instance_id=instance_id, start_at=start_at)

    def get_workflow_state(self, instance_id: str, *,
                           fetch_payloads: bool = True) -> Optional[WorkflowState]:
        """Fetches runtime state for the specified workflow instance.

        Args:
            instanceId: The unique ID of the workflow instance to fetch.
            fetch_payloads: If true, fetches the input, output payloads and custom status
            for the workflow instance. Defaults to false.

        Returns:
            The current state of the workflow instance, or None if the workflow instance does not
            exist.

        """
        state = self.__obj.get_orchestration_state(instance_id, fetch_payloads=fetch_payloads)
        return WorkflowState(state) if state else None

    def wait_for_workflow_start(self, instance_id: str, *, fetch_payloads: bool = False,
                                timeout_in_seconds: int = 60) -> Optional[WorkflowState]:
        """Waits for a workflow to start running and returns a WorkflowState object that contains
           metadata about the started workflow.

           A "started" workflow instance is any instance not in the WorkflowRuntimeStatus.Pending
           state. This method will return a completed task if the workflow has already started
           running or has already completed.

        Args:
            instance_id: The unique ID of the workflow instance to wait for.
            fetch_payloads: If true, fetches the input, output payloads and custom status for
            the workflow instance. Defaults to false.
            timeout_in_seconds: The maximum time to wait for the workflow instance to start running.
            Defaults to 60 seconds.

        Returns:
            WorkflowState record that describes the workflow instance and its execution status.
            If the specified workflow isn't found, the WorkflowState.Exists value will be false.
        """
        state = self.__obj.wait_for_orchestration_start(instance_id, fetch_payloads=fetch_payloads,
                                                        timeout=timeout_in_seconds)
        return WorkflowState(state) if state else None

    def wait_for_workflow_completion(self, instance_id: str, *, fetch_payloads: bool = True,
                                     timeout_in_seconds: int = 60) -> Optional[WorkflowState]:
        """Waits for a workflow to complete and returns a WorkflowState object that contains
           metadata about the started instance.

           A "completed" workflow instance is any instance in one of the terminal states. For
           example, the WorkflowRuntimeStatus.Completed, WorkflowRuntimeStatus.Failed or
           WorkflowRuntimeStatus.Terminated states.

           Workflows are long-running and could take hours, days, or months before completing.
           Workflows can also be eternal, in which case they'll never complete unless terminated.
           In such cases, this call may block indefinitely, so care must be taken to ensure
           appropriate timeouts are enforced using timeout parameter.

           If a workflow instance is already complete when this method is called, the method
           will return immediately.

        Args:
            instance_id: The unique ID of the workflow instance to wait for.
            fetch_payloads: If true, fetches the input, output payloads and custom status
            for the workflow instance. Defaults to true.
            timeout_in_seconds: The maximum time in seconds to wait for the workflow instance to
            complete. Defaults to 60 seconds.

        Returns:
            WorkflowState record that describes the workflow instance and its execution status.
        """
        state = self.__obj.wait_for_orchestration_completion(instance_id,
                                                             fetch_payloads=fetch_payloads,
                                                             timeout=timeout_in_seconds)
        return WorkflowState(state) if state else None

    def raise_workflow_event(self, instance_id: str, event_name: str, *,
                             data: Optional[Any] = None):
        """Sends an event notification message to a waiting workflow instance.
           In order to handle the event, the target workflow instance must be waiting for an
           event named value of "eventName" param using the wait_for_external_event API.
           If the target workflow instance is not yet waiting for an event named param "eventName"
           value, then the event will be saved in the workflow instance state and dispatched
           immediately when the workflow calls wait_for_external_event.
           This event saving occurs even if the workflow has canceled its wait operation before
           the event was received.

           Workflows can wait for the same event name multiple times, so sending multiple events
           with the same name is allowed. Each external event received by a workflow will complete
           just one task returned by the wait_for_external_event method.

           Raised events for a completed or non-existent workflow instance will be silently
           discarded.

        Args:
            instanceId: The ID of the workflow instance that will handle the event.
            eventName: The name of the event. Event names are case-insensitive.
            data: The serializable data payload to include with the event.
        """
        return self.__obj.raise_orchestration_event(instance_id, event_name, data=data)

    def terminate_workflow(self, instance_id: str, *, output: Optional[Any] = None):
        """Terminates a running workflow instance and updates its runtime status to
           WorkflowRuntimeStatus.Terminated This method internally enqueues a "terminate" message in
           the task hub. When the task hub worker processes this message, it will update the runtime
           status of the target instance to WorkflowRuntimeStatus.Terminated. You can use
           wait_for_workflow_completion to wait for the instance to reach the terminated state.

           Terminating a workflow instance has no effect on any in-flight activity function
           executions or child workflows that were started by the terminated instance. Those
           actions will continue to run without interruption. However, their results will be
           discarded. If you want to terminate child-workflows, you must issue separate terminate
           commands for each child workflow instance individually.

           At the time of writing, there is no way to terminate an in-flight activity execution.

        Args:
            instance_id: The ID of the workflow instance to terminate.
            output: The optional output to set for the terminated workflow instance.
       """
        return self.__obj.terminate_orchestration(instance_id, output=output)

    def pause_workflow(self, instance_id: str):
        """Suspends a workflow instance, halting processing of it until resume_workflow is used to
           resume the workflow.

        Args:
            instance_id: The instance ID of the workflow to suspend.
        """
        return self.__obj.suspend_orchestration(instance_id)

    def resume_workflow(self, instance_id: str):
        """Resumes a workflow instance that was suspended via pause_workflow.

        Args:
            instance_id: The instance ID of the workflow to resume.
        """
        return self.__obj.resume_orchestration(instance_id)
