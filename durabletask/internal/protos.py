# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Re-exports all generated protobuf symbols from the split proto modules into
# a single namespace, preserving backwards compatibility for code that imports
# this module as `pb` and accesses types like `pb.HistoryEvent`.
from durabletask.internal.history_events_pb2 import *  # noqa: F401, F403
from durabletask.internal.orchestration_pb2 import *  # noqa: F401, F403
from durabletask.internal.orchestrator_actions_pb2 import *  # noqa: F401, F403
from durabletask.internal.orchestrator_service_pb2 import *  # noqa: F401, F403
