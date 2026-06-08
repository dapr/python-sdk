# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

import base64
import json
from typing import Any, Dict, Mapping, Optional

from google.protobuf import any_pb2, wrappers_pb2
from grpc import StatusCode  # type: ignore[attr-defined]

from dapr.actor.runtime.config import (
    ActorReentrancyConfig,
    ActorRuntimeConfig,
    ActorTypeConfig,
)
from dapr.clients.base import DAPR_REENTRANCY_ID_HEADER
from dapr.clients.exceptions import ERROR_CODE_UNKNOWN, DaprInternalError
from dapr.proto import api_v1

CONTENT_TYPE_HEADER = 'content-type'
JSON_CONTENT_TYPE = 'application/json'


def build_initial_request(
    config: ActorRuntimeConfig,
) -> api_v1.SubscribeActorEventsRequestInitialAlpha1:
    """Builds the stream registration message from the actor runtime config.

    This is the gRPC equivalent of the JSON payload served by the HTTP
    ``GET /dapr/config`` endpoint. ``actor_scan_interval`` and
    ``reminders_storage_partitions`` have no counterpart in the proto
    contract and are not transmitted.
    """
    config_entities = {type_config.actor_type for type_config in config.actor_type_configs}
    entities = sorted(config.entities | config_entities)

    initial_request = api_v1.SubscribeActorEventsRequestInitialAlpha1(entities=entities)

    if config.actor_idle_timeout is not None:
        initial_request.actor_idle_timeout.FromTimedelta(config.actor_idle_timeout)
    if config.drain_ongoing_call_timeout is not None:
        initial_request.drain_ongoing_call_timeout.FromTimedelta(config.drain_ongoing_call_timeout)
    if config.drain_rebalanced_actors is not None:
        initial_request.drain_rebalanced_actors = config.drain_rebalanced_actors
    if config.reentrancy is not None:
        initial_request.reentrancy.CopyFrom(_reentrancy_to_proto(config.reentrancy))

    for type_config in config.actor_type_configs:
        initial_request.entities_config.append(_entity_config_to_proto(type_config))

    return initial_request


def _reentrancy_to_proto(reentrancy: ActorReentrancyConfig) -> api_v1.ActorReentrancyConfig:
    return api_v1.ActorReentrancyConfig(
        enabled=reentrancy.enabled,
        max_stack_depth=reentrancy.max_stack_depth,
    )


def _entity_config_to_proto(type_config: ActorTypeConfig) -> api_v1.ActorEntityConfig:
    proto_config = api_v1.ActorEntityConfig(entities=[type_config.actor_type])

    if type_config.actor_idle_timeout is not None:
        proto_config.actor_idle_timeout.FromTimedelta(type_config.actor_idle_timeout)
    if type_config.drain_ongoing_call_timeout is not None:
        proto_config.drain_ongoing_call_timeout.FromTimedelta(
            type_config.drain_ongoing_call_timeout
        )
    if type_config.drain_rebalanced_actors is not None:
        proto_config.drain_rebalanced_actors = type_config.drain_rebalanced_actors
    if type_config.reentrancy is not None:
        proto_config.reentrancy.CopyFrom(_reentrancy_to_proto(type_config.reentrancy))

    return proto_config


def extract_reentrancy_id(metadata: Mapping[str, str]) -> Optional[str]:
    """Looks up the reentrancy id header case-insensitively in callback metadata."""
    for key, value in metadata.items():
        if key.lower() == DAPR_REENTRANCY_ID_HEADER.lower():
            return value
    return None


def build_reminder_fire_body(
    reminder_request: api_v1.SubscribeActorEventsResponseReminderRequestAlpha1,
) -> bytes:
    """Synthesizes the JSON body ``ActorRuntime.fire_reminder`` expects.

    Over HTTP, daprd delivers reminder fires as a JSON object with the
    registered data embedded verbatim as the ``data`` value (for SDK-registered
    reminders, a base64 string). The stream carries the same payload inside a
    ``google.protobuf.Any``, so the JSON value is embedded unchanged.
    """
    body: Dict[str, Any] = {
        'dueTime': reminder_request.due_time,
        'period': reminder_request.period,
    }
    data_value = _any_to_json_value(reminder_request)
    if data_value is not None:
        body['data'] = _parse_json_value(data_value, 'reminder')
    return json.dumps(body).encode('utf-8')


def build_timer_fire_body(
    timer_request: api_v1.SubscribeActorEventsResponseTimerRequestAlpha1,
) -> bytes:
    """Synthesizes the JSON body ``ActorRuntime.fire_timer`` expects.

    Timers registered through ``DaprActorGrpcClient`` arrive base64-wrapped
    because daprd JSON-marshals the raw bytes of the unary
    ``RegisterActorTimer`` request, so the original JSON value is recovered
    before embedding (see ``_maybe_unwrap_grpc_registered_value``).
    """
    body: Dict[str, Any] = {
        'callback': timer_request.callback,
        'dueTime': timer_request.due_time,
        'period': timer_request.period,
        'data': None,
    }
    data_value = _any_to_json_value(timer_request)
    if data_value is not None:
        data_value = _maybe_unwrap_grpc_registered_value(data_value)
        body['data'] = _parse_json_value(data_value, 'timer')
    return json.dumps(body).encode('utf-8')


def _parse_json_value(value: bytes, callback_kind: str) -> Any:
    """Parses a callback data payload, failing with a clear error message."""
    try:
        return json.loads(value)
    except ValueError as error:
        raise ValueError(f'{callback_kind} data is not valid JSON: {error}') from error


def _any_to_json_value(callback_request: Any) -> Optional[bytes]:
    """Extracts the raw JSON value bytes from a callback's ``Any`` data field.

    daprd stores reminder/timer payloads as a ``google.protobuf.BytesValue``
    holding the JSON value registered by the app, and unwraps it the same way
    when delivering over HTTP (see Reminder.MarshalJSON in dapr/dapr). An
    ``Any`` of any other type falls back to its raw value bytes.
    """
    if not callback_request.HasField('data'):
        return None

    data: any_pb2.Any = callback_request.data
    if data.Is(wrappers_pb2.BytesValue.DESCRIPTOR):
        bytes_value = wrappers_pb2.BytesValue()
        data.Unpack(bytes_value)
        return bytes_value.value or None
    return data.value or None


def _maybe_unwrap_grpc_registered_value(value: bytes) -> bytes:
    """Recovers the original JSON value from a gRPC-registered timer payload.

    daprd's unary ``RegisterActorTimer`` JSON-marshals the request's raw
    bytes, turning a JSON value ``J`` into the string ``base64(J)``. When the
    stored value is a JSON string that base64-decodes to valid JSON, the
    decoded form is the original registration payload. HTTP-registered string
    payloads that coincidentally satisfy both checks are misdetected; this is
    a documented limitation of the alpha transport.
    """
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    if not isinstance(parsed, str):
        return value
    try:
        decoded = base64.b64decode(parsed, validate=True)
        json.loads(decoded)
    except Exception:  # noqa: BLE001
        return value
    return decoded


def build_invoke_error_payload(exception: Exception) -> bytes:
    """Serializes a handler exception the way the HTTP extensions do.

    Matches the 500-response body shape of the FastAPI/Flask actor
    extensions so callers observe the same error payload on both transports.
    """
    if isinstance(exception, DaprInternalError):
        payload = exception.as_json_safe_dict()
    else:
        payload = {'message': repr(exception), 'errorCode': ERROR_CODE_UNKNOWN}
    return json.dumps(payload).encode('utf-8')


def status_code_for_exception(exception: Exception) -> int:
    """Maps a dispatch exception to the gRPC status code for ``request_failed``.

    ``ValueError`` (unregistered actor type) and ``AttributeError`` (unknown
    actor method) map to ``NOT_FOUND``, which daprd treats as a permanent,
    non-retryable failure. Everything else maps to ``UNKNOWN``.
    """
    if isinstance(exception, (ValueError, AttributeError)):
        return StatusCode.NOT_FOUND.value[0]
    return StatusCode.UNKNOWN.value[0]
