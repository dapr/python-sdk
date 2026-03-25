# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Re-exports all generated protobuf symbols from the split proto modules into
# a single namespace, preserving backwards compatibility for code that imports
# this module as `pb` and accesses types like `pb.HistoryEvent`.

# Well-known protobuf types must be registered in the descriptor pool before
# the generated pb2 files that depend on them are loaded.
from google.protobuf import duration_pb2, empty_pb2, timestamp_pb2, wrappers_pb2  # noqa: F401

from durabletask.internal.orchestration_pb2 import *  # noqa: F401, F403
from durabletask.internal.history_events_pb2 import *  # noqa: F401, F403
from durabletask.internal.orchestrator_actions_pb2 import *  # noqa: F401, F403
from durabletask.internal.orchestrator_service_pb2 import *  # noqa: F401, F403
