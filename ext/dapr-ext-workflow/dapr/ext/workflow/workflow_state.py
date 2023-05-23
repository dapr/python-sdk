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
    """Represents a snapshot of a workflow instance's current state, including runtime status."""

    def __init__(self, state: client.OrchestrationState):
        self.__obj = state

    # provide proxy access to regular attributes of wrapped object
    def __getattr__(self, name):
        return getattr(self.__obj, name)

    @property
    def runtime_status(self) -> WorkflowStatus:
        if self.__obj.runtime_status == client.OrchestrationStatus.RUNNING:
            return WorkflowStatus.RUNNING
        elif self.__obj.runtime_status == client.OrchestrationStatus.COMPLETED:
            return WorkflowStatus.COMPLETED
        elif self.__obj.runtime_status == client.OrchestrationStatus.FAILED:
            return WorkflowStatus.FAILED
        elif self.__obj.runtime_status == client.OrchestrationStatus.TERMINATED:
            return WorkflowStatus.TERMINATED
        elif self.__obj.runtime_status == client.OrchestrationStatus.PENDING:
            return WorkflowStatus.PENDING
        elif self.__obj.runtime_status == client.OrchestrationStatus.SUSPENDED:
            return WorkflowStatus.SUSPENDED
        else:
            return WorkflowStatus.UNKNOWN
