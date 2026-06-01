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

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional, Sequence, Union

import dapr.ext.workflow._durabletask.internal.helpers as helpers
import dapr.ext.workflow._durabletask.internal.orchestrator_service_pb2_grpc as stubs
import dapr.ext.workflow._durabletask.internal.protos as pb
import dapr.ext.workflow._durabletask.internal.shared as shared
import grpc
from dapr.ext.workflow._durabletask import task
from dapr.ext.workflow._durabletask.aio.internal.grpc_interceptor import (
    DefaultClientInterceptorImpl,
)
from dapr.ext.workflow._durabletask.aio.internal.shared import (
    ClientInterceptor,
    get_grpc_aio_channel,
)
from dapr.ext.workflow._durabletask.client import (
    OrchestrationStatus,
    TInput,
    TOutput,
    WorkflowIdReusePolicy,
    WorkflowState,
    _TransientTimeout,
    new_orchestration_state,
)
from google.protobuf import wrappers_pb2

# If `opentelemetry-instrumentation-grpc` is available, enable the gRPC client interceptor
try:
    from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient

    GrpcInstrumentorClient().instrument()
except ImportError:
    pass


class AsyncTaskHubGrpcClient:
    def __init__(
        self,
        *,
        host_address: Optional[str] = None,
        metadata: Optional[list[tuple[str, str]]] = None,
        log_handler: Optional[logging.Handler] = None,
        log_formatter: Optional[logging.Formatter] = None,
        secure_channel: bool = False,
        interceptors: Optional[Sequence[ClientInterceptor]] = None,
        channel_options: Optional[Sequence[tuple[str, Any]]] = None,
    ):
        if interceptors is not None:
            interceptors = list(interceptors)
            if metadata is not None:
                interceptors.append(DefaultClientInterceptorImpl(metadata))
        elif metadata is not None:
            interceptors = [DefaultClientInterceptorImpl(metadata)]
        else:
            interceptors = None

        channel = get_grpc_aio_channel(
            host_address=host_address,
            secure_channel=secure_channel,
            interceptors=interceptors,
            options=channel_options,
        )
        self._channel = channel
        self._stub = stubs.TaskHubSidecarServiceStub(channel)
        self._logger = shared.get_logger('client', log_handler, log_formatter)

    async def aclose(self):
        await self._channel.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
        return False

    async def schedule_new_orchestration(
        self,
        orchestrator: Union[task.Orchestrator[TInput, TOutput], str],
        *,
        input: Optional[TInput] = None,
        instance_id: Optional[str] = None,
        start_at: Optional[datetime] = None,
        reuse_id_policy: Optional[WorkflowIdReusePolicy] = None,
    ) -> str:
        name = orchestrator if isinstance(orchestrator, str) else task.get_name(orchestrator)

        req = pb.CreateInstanceRequest(
            name=name,
            instanceId=instance_id if instance_id else uuid.uuid4().hex,
            input=wrappers_pb2.StringValue(value=shared.to_json(input))
            if input is not None
            else None,
            scheduledStartTimestamp=helpers.new_timestamp(start_at) if start_at else None,
            version=helpers.get_string_value(None),
        )

        self._logger.info(f"Starting new '{name}' instance with ID = '{req.instanceId}'.")
        res: pb.CreateInstanceResponse = await self._stub.StartInstance(req)
        return res.instanceId

    async def get_orchestration_state(
        self, instance_id: str, *, fetch_payloads: bool = True
    ) -> Optional[WorkflowState]:
        req = pb.GetInstanceRequest(instanceId=instance_id, getInputsAndOutputs=fetch_payloads)
        res: pb.GetInstanceResponse = await self._stub.GetInstance(req)
        return new_orchestration_state(req.instanceId, res)

    async def wait_for_orchestration_start(
        self, instance_id: str, *, fetch_payloads: bool = False, timeout: int = 0
    ) -> Optional[WorkflowState]:
        req = pb.GetInstanceRequest(instanceId=instance_id, getInputsAndOutputs=fetch_payloads)
        self._logger.info(
            f"Waiting {'indefinitely' if timeout in (0, None) else f'up to {timeout}s'} for instance '{instance_id}' to start."
        )

        async def _call(grpc_timeout):
            res: pb.GetInstanceResponse = await self._stub.WaitForInstanceStart(
                req, timeout=grpc_timeout
            )
            return new_orchestration_state(req.instanceId, res)

        try:
            return await self._call_with_transient_retry(instance_id, timeout, _call)
        except _TransientTimeout:
            raise TimeoutError('Timed-out waiting for the orchestration to start')

    async def wait_for_orchestration_completion(
        self, instance_id: str, *, fetch_payloads: bool = True, timeout: int = 0
    ) -> Optional[WorkflowState]:
        req = pb.GetInstanceRequest(instanceId=instance_id, getInputsAndOutputs=fetch_payloads)
        self._logger.info(
            f"Waiting {'indefinitely' if timeout in (0, None) else f'up to {timeout}s'} for instance '{instance_id}' to complete."
        )

        async def _call(grpc_timeout):
            res: pb.GetInstanceResponse = await self._stub.WaitForInstanceCompletion(
                req, timeout=grpc_timeout
            )
            state = new_orchestration_state(req.instanceId, res)
            if not state:
                return None

            if (
                state.runtime_status == OrchestrationStatus.FAILED
                and state.failure_details is not None
            ):
                details = state.failure_details
                self._logger.info(
                    f"Instance '{instance_id}' failed: [{details.error_type}] {details.message}"
                )
            elif state.runtime_status == OrchestrationStatus.TERMINATED:
                self._logger.info(f"Instance '{instance_id}' was terminated.")
            elif state.runtime_status == OrchestrationStatus.COMPLETED:
                self._logger.info(f"Instance '{instance_id}' completed.")
            return state

        try:
            return await self._call_with_transient_retry(instance_id, timeout, _call)
        except _TransientTimeout:
            raise TimeoutError('Timed-out waiting for the orchestration to complete')

    # Transient gRPC codes that indicate the workflow runtime is temporarily
    # unable to locate the workflow actor — typically immediately after a Dapr
    # sidecar restart (e.g. recovery from chaos). The placement service has the
    # actor registration, but local daprd hasn't received the dissemination yet.
    # Without retry, every poll fails permanently with FAILED_PRECONDITION even
    # though the workflow runtime state is intact.
    _TRANSIENT_RPC_CODES = (
        grpc.StatusCode.FAILED_PRECONDITION,
        grpc.StatusCode.UNAVAILABLE,
    )

    async def _call_with_transient_retry(self, instance_id, timeout, call_fn):
        """Async mirror of TaskHubGrpcClient._call_with_transient_retry.
        Retries FAILED_PRECONDITION/UNAVAILABLE with capped exponential
        backoff while clamping sleep and per-call gRPC timeout to the
        remaining budget. The first call passes ``timeout`` verbatim so
        callers observe identical behavior on a healthy runtime.
        """
        unbounded = timeout in (0, None)
        deadline = None if unbounded else time.monotonic() + timeout
        grpc_timeout = None if unbounded else timeout
        backoff = 0.5
        while True:
            try:
                return await call_fn(grpc_timeout)
            except grpc.RpcError as rpc_error:
                code = rpc_error.code()  # type: ignore
                if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                    raise _TransientTimeout()
                if code not in self._TRANSIENT_RPC_CODES:
                    raise

                if deadline is None:
                    remaining = None
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise _TransientTimeout()

                sleep_for = min(backoff, 5.0)
                if remaining is not None:
                    sleep_for = min(sleep_for, remaining)
                self._logger.warning(
                    f"Transient gRPC error {code.name} waiting on instance '{instance_id}'; "
                    f'retrying in {sleep_for:.2f}s'
                )
                await asyncio.sleep(sleep_for)
                backoff = min(backoff * 2, 5.0)

                if deadline is None:
                    grpc_timeout = None
                else:
                    grpc_timeout = deadline - time.monotonic()
                    if grpc_timeout <= 0:
                        raise _TransientTimeout()

    async def raise_orchestration_event(
        self, instance_id: str, event_name: str, *, data: Optional[Any] = None
    ):
        req = pb.RaiseEventRequest(
            instanceId=instance_id,
            name=event_name,
            input=wrappers_pb2.StringValue(value=shared.to_json(data)) if data else None,
        )

        self._logger.info(f"Raising event '{event_name}' for instance '{instance_id}'.")
        await self._stub.RaiseEvent(req)

    async def terminate_orchestration(
        self, instance_id: str, *, output: Optional[Any] = None, recursive: bool = True
    ):
        req = pb.TerminateRequest(
            instanceId=instance_id,
            output=wrappers_pb2.StringValue(value=shared.to_json(output)) if output else None,
            recursive=recursive,
        )

        self._logger.info(f"Terminating instance '{instance_id}'.")
        await self._stub.TerminateInstance(req)

    async def suspend_orchestration(self, instance_id: str):
        req = pb.SuspendRequest(instanceId=instance_id)
        self._logger.info(f"Suspending instance '{instance_id}'.")
        await self._stub.SuspendInstance(req)

    async def resume_orchestration(self, instance_id: str):
        req = pb.ResumeRequest(instanceId=instance_id)
        self._logger.info(f"Resuming instance '{instance_id}'.")
        await self._stub.ResumeInstance(req)

    async def purge_orchestration(self, instance_id: str, recursive: bool = True):
        req = pb.PurgeInstancesRequest(instanceId=instance_id, recursive=recursive)
        self._logger.info(f"Purging instance '{instance_id}'.")
        await self._stub.PurgeInstances(req)
