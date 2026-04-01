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

# Re-exports all generated protobuf symbols from the split proto modules into
# a single namespace, preserving backwards compatibility for code that imports
# this module as `pb` and accesses types like `pb.HistoryEvent`.

# isort: skip_file
# The import order below is intentional and must not be changed.
# Well-known protobuf types must be registered in the descriptor pool before
# the generated pb2 files that depend on them are loaded. Additionally,
# orchestration_pb2 must be loaded before history_events_pb2, which depends on it.
from google.protobuf import duration_pb2, empty_pb2, timestamp_pb2, wrappers_pb2  # noqa: F401
from dapr.ext.workflow._durabletask.internal.orchestration_pb2 import *  # noqa: F401, F403
from dapr.ext.workflow._durabletask.internal.history_events_pb2 import *  # noqa: F401, F403
from dapr.ext.workflow._durabletask.internal.orchestrator_actions_pb2 import *  # noqa: F401, F403
from dapr.ext.workflow._durabletask.internal.orchestrator_service_pb2 import *  # noqa: F401, F403
