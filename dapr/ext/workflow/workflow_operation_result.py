# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Return types for the ``*_with_result`` methods of the workflow clients.

Each one carries ``staged``. A sidecar with the ``WorkflowsStagedOperations``
preview feature on accepts a workflow operation even when no workflow worker is
connected. It saves the operation and runs it once a worker connects. Such an
operation is staged. ``staged`` is False when the operation ran at once, and on
sidecars that never stage operations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowScheduleResult:
    """The outcome of scheduling a new workflow instance.

    Attributes:
        instance_id: The ID of the scheduled workflow instance.
        staged: True when the sidecar saved the start to run once a workflow
            worker connects, rather than starting the instance at once.
    """

    instance_id: str
    staged: bool


@dataclass(frozen=True)
class WorkflowOperationResult:
    """The outcome of raising an event on, terminating, pausing or resuming a workflow.

    Attributes:
        staged: True when the sidecar saved the operation to run once a workflow
            worker connects, rather than applying it at once.
    """

    staged: bool


@dataclass(frozen=True)
class WorkflowRerunResult:
    """The outcome of rerunning a workflow instance from an event.

    Attributes:
        new_instance_id: The ID of the new workflow instance.
        staged: True when the sidecar saved the rerun to run once a workflow
            worker connects, rather than starting it at once.
    """

    new_instance_id: str
    staged: bool
