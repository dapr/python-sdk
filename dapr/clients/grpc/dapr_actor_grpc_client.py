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
from typing import Any, Dict, Optional

import grpc.aio  # type: ignore
from google.protobuf import any_pb2
from grpc import StatusCode  # type: ignore[attr-defined]
from grpc.aio import AioRpcError

from dapr.clients.base import DAPR_REENTRANCY_ID_HEADER, DaprActorClientBase
from dapr.clients.exceptions import DaprInternalError
from dapr.clients.grpc._channel import create_aio_channel
from dapr.common.reentrancy_context import reentrancy_ctx
from dapr.proto import api_service_v1, api_v1, common_v1
from dapr.serializers import DefaultJSONSerializer, Serializer
from dapr.serializers.util import convert_from_dapr_duration


class DaprActorGrpcClient(DaprActorClientBase):
    """A Dapr Actor gRPC client implementing :class:`DaprActorClientBase`.

    Alpha: performs the outbound actor operations (invoke, state, reminders,
    timers) over the unary RPCs of daprd's gRPC API instead of the actor HTTP
    endpoints. Used by :class:`ActorGrpcHost` so actor apps hosted over the
    ``SubscribeActorEventsAlpha1`` stream never need daprd's HTTP port.

    Unlike the HTTP client, which forwards the runtime's already-serialized
    request body verbatim, this client unpacks the body into proto fields and
    must re-serialize the embedded JSON values. It does so with the same
    serializer the runtime used so the bytes daprd persists (state) or echoes
    back (timer data) stay identical to the HTTP transport's.
    """

    def __init__(
        self,
        timeout: int = 60,
        address: Optional[str] = None,
        channel: Optional[grpc.aio.Channel] = None,
        serializer: Serializer = DefaultJSONSerializer(),
    ):
        """Creates the gRPC actor client.

        Args:
            timeout (int): per-call timeout in seconds.
            address (str, optional): Dapr runtime gRPC address; defaults to the
                same resolution as the Dapr clients (DAPR_GRPC_ENDPOINT et al).
            channel (grpc.aio.Channel, optional): externally owned channel to
                reuse; when provided ``address`` is ignored and ``close()``
                leaves the channel open.
            serializer (Serializer): serializer used to re-encode the JSON
                values unpacked from request bodies; must match the runtime's
                so persisted/echoed bytes are identical to the HTTP transport.
        """
        self._timeout = timeout
        self._serializer = serializer
        self._owns_channel = channel is None
        self._channel = channel if channel is not None else create_aio_channel(address)
        self._stub = api_service_v1.DaprStub(self._channel)

    async def close(self) -> None:
        """Closes the underlying channel when this client created it."""
        if self._owns_channel:
            await self._channel.close()

    async def invoke_method(
        self, actor_type: str, actor_id: str, method: str, data: Optional[bytes] = None
    ) -> bytes:
        """Invokes a method on an actor through the InvokeActor RPC.

        The reentrancy id, when present in the current context, is propagated
        in the request metadata map under the same header name the HTTP
        transport uses.
        """
        metadata: Dict[str, str] = {}
        reentrancy_id = reentrancy_ctx.get()
        if reentrancy_id:
            metadata[DAPR_REENTRANCY_ID_HEADER] = reentrancy_id

        request = api_v1.InvokeActorRequest(
            actor_type=actor_type,
            actor_id=actor_id,
            method=method,
            data=data or b'',
            metadata=metadata,
        )
        response = await self._stub.InvokeActor(request, timeout=self._timeout)
        return response.data

    async def save_state_transactionally(self, actor_type: str, actor_id: str, data: bytes) -> None:
        """Saves state through the ExecuteActorStateTransaction RPC.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            data (bytes): Json-serialized the transactional state operations.
        """
        operations_raw = json.loads(data)
        operations = [_to_transactional_operation(op, self._serializer) for op in operations_raw]
        request = api_v1.ExecuteActorStateTransactionRequest(
            actor_type=actor_type,
            actor_id=actor_id,
            operations=operations,
        )
        await self._stub.ExecuteActorStateTransaction(request, timeout=self._timeout)

    async def get_state(self, actor_type: str, actor_id: str, name: str) -> bytes:
        """Gets a state value through the GetActorState RPC.

        Returns empty bytes when the key does not exist, matching the HTTP
        client's empty-body behavior.
        """
        request = api_v1.GetActorStateRequest(actor_type=actor_type, actor_id=actor_id, key=name)
        try:
            response = await self._stub.GetActorState(request, timeout=self._timeout)
        except AioRpcError as error:
            if error.code() == StatusCode.NOT_FOUND:
                return b''
            raise
        return response.data

    async def register_reminder(
        self, actor_type: str, actor_id: str, name: str, data: bytes
    ) -> None:
        """Registers a reminder through the RegisterActorReminder RPC.

        Args:
            actor_type (str): Actor type.
            actor_id (str): Id of Actor type.
            name (str): The name of reminder
            data (bytes): Reminder request json body.
        """
        reminder = json.loads(data)
        request = api_v1.RegisterActorReminderRequest(
            actor_type=actor_type,
            actor_id=actor_id,
            name=name,
            due_time=reminder['dueTime'],
            period=reminder.get('period') or '',
            ttl=reminder.get('ttl') or '',
            data=_decode_reminder_state(reminder.get('data')),
        )
        failure_policy = _to_failure_policy(reminder.get('failurePolicy'))
        if failure_policy is not None:
            request.failure_policy.CopyFrom(failure_policy)
        await self._stub.RegisterActorReminder(request, timeout=self._timeout)

    async def unregister_reminder(self, actor_type: str, actor_id: str, name: str) -> None:
        """Unregisters a reminder through the UnregisterActorReminder RPC."""
        request = api_v1.UnregisterActorReminderRequest(
            actor_type=actor_type, actor_id=actor_id, name=name
        )
        await self._stub.UnregisterActorReminder(request, timeout=self._timeout)

    async def register_timer(self, actor_type: str, actor_id: str, name: str, data: bytes) -> None:
        """Registers a timer through the RegisterActorTimer RPC.

        The timer's ``data`` JSON value is sent as raw JSON bytes; daprd
        base64-wraps them and ``ActorGrpcHost`` recovers the original value
        when the timer fires.
        """
        timer = json.loads(data)
        timer_state = timer.get('data')
        request = api_v1.RegisterActorTimerRequest(
            actor_type=actor_type,
            actor_id=actor_id,
            name=name,
            due_time=timer['dueTime'],
            period=timer.get('period') or '',
            ttl=timer.get('ttl') or '',
            callback=timer.get('callback') or '',
            data=self._serializer.serialize(timer_state),
        )
        await self._stub.RegisterActorTimer(request, timeout=self._timeout)

    async def unregister_timer(self, actor_type: str, actor_id: str, name: str) -> None:
        """Unregisters a timer through the UnregisterActorTimer RPC."""
        request = api_v1.UnregisterActorTimerRequest(
            actor_type=actor_type, actor_id=actor_id, name=name
        )
        await self._stub.UnregisterActorTimer(request, timeout=self._timeout)


def _to_transactional_operation(
    operation: Dict[str, Any],
    serializer: Serializer,
) -> api_v1.TransactionalActorStateOperation:
    """Converts one JSON transactional operation into its proto form.

    The JSON shape is produced by ``StateProvider.save_state``; the value is
    re-serialized with the runtime's serializer into raw JSON bytes, which
    daprd stores verbatim — byte-identical to what the HTTP endpoint persists.
    """
    request: Dict[str, Any] = operation['request']

    proto_operation = api_v1.TransactionalActorStateOperation(
        operationType=operation['operation'],
        key=request['key'],
    )
    if 'value' in request:
        value_bytes = serializer.serialize(request['value'])
        proto_operation.value.CopyFrom(any_pb2.Any(value=value_bytes))
    metadata: Optional[Dict[str, str]] = request.get('metadata')
    if metadata:
        proto_operation.metadata.update(metadata)
    return proto_operation


def _decode_reminder_state(encoded_state: Optional[str]) -> bytes:
    """Recovers raw reminder state bytes from the JSON body's base64 field.

    daprd JSON-marshals the raw bytes of the unary request — Go encodes
    ``[]byte`` as a base64 string — so sending the decoded bytes makes the
    stored JSON value identical to what the HTTP endpoint persists.
    """
    if not encoded_state:
        return b''
    return base64.b64decode(encoded_state)


def _to_failure_policy(policy: Optional[Dict[str, Any]]) -> Optional[common_v1.JobFailurePolicy]:
    """Converts the failure policy dict from the reminder JSON body to proto."""
    if policy is None:
        return None
    if 'drop' in policy:
        return common_v1.JobFailurePolicy(drop=common_v1.JobFailurePolicyDrop())

    constant = policy.get('constant')
    if constant is None:
        raise DaprInternalError(f'unsupported reminder failure policy: {policy}')

    proto_constant = common_v1.JobFailurePolicyConstant()
    interval: Optional[str] = constant.get('interval')
    if interval is not None:
        proto_constant.interval.FromTimedelta(convert_from_dapr_duration(interval))
    max_retries: Optional[int] = constant.get('maxRetries')
    if max_retries is not None:
        proto_constant.max_retries = max_retries
    return common_v1.JobFailurePolicy(constant=proto_constant)
