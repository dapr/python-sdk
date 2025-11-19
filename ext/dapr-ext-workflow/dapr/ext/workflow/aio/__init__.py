"""
Copyright 2025 The Dapr Authors
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

# Note: Do not import WorkflowRuntime here to avoid circular imports
# Re-export async context and awaitables
from .async_context import AsyncWorkflowContext  # noqa: F401
from .async_driver import CoroutineOrchestratorRunner  # noqa: F401
from .awaitables import (  # noqa: F401
    ActivityAwaitable,
    SleepAwaitable,
    SubOrchestratorAwaitable,
    WhenAllAwaitable,
    WhenAnyAwaitable,
)

"""
Async I/O surface for Dapr Workflow extension.

This package provides explicit async-focused imports that mirror the top-level
exports, improving discoverability and aligning with dapr.aio patterns.
"""

__all__ = [
    'AsyncWorkflowContext',
    'CoroutineOrchestratorRunner',
    'ActivityAwaitable',
    'SubOrchestratorAwaitable',
    'SleepAwaitable',
    'WhenAllAwaitable',
    'WhenAnyAwaitable',
]
