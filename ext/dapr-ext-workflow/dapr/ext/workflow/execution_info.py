"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

from dataclasses import dataclass

"""
Minimal, deterministic snapshots of inbound durable metadata.

Rationale
---------

Execution info previously mirrored many engine fields (IDs, tracing, attempts) already
available on the workflow/activity contexts. To remove redundancy and simplify usage, the
execution info types now only capture the durable ``inbound_metadata`` that was actually
propagated into this activation. Use context properties directly for engine fields.
"""


@dataclass
class WorkflowExecutionInfo:
    """Per-activation snapshot for workflows.

    Only includes ``inbound_metadata`` that arrived with this activation.
    """

    inbound_metadata: dict[str, str]


@dataclass
class ActivityExecutionInfo:
    """Per-activation snapshot for activities.

    Only includes ``inbound_metadata`` that arrived with this activity invocation.
    """

    inbound_metadata: dict[str, str]
    activity_name: str
