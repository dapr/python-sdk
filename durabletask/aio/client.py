# Copyright (c) The Dapr Authors.
# Licensed under the MIT License.

import logging
import uuid
from datetime import datetime
from typing import Any, Optional, Sequence, Union

import grpc
from google.protobuf import wrappers_pb2

import durabletask.internal.helpers as helpers
import durabletask.internal.orchestrator_service_pb2 as pb
import durabletask.internal.orchestrator_service_pb2_grpc as stubs
import durabletask.internal.shared as shared
from durabletask import task
from durabletask.aio.internal.grpc_interceptor import DefaultClientInterceptorImpl
from durabletask.aio.internal.shared import ClientInterceptor, get_grpc_aio_channel
from durabletask.client import (
    OrchestrationState,
    OrchestrationStatus,
    TInput,
    TOutput,
    new_orchestration_state,
)

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
        self._logger = shared.get_logger("client", log_handler, log_formatter)

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
        reuse_id_policy: Optional[pb.OrchestrationIdReusePolicy] = None,
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
            orchestrationIdReusePolicy=reuse_id_policy,
        )

        self._logger.info(f"Starting new '{name}' instance with ID = '{req.instanceId}'.")
        res: pb.CreateInstanceResponse = await self._stub.StartInstance(req)
        return res.instanceId

    async def get_orchestration_state(
        self, instance_id: str, *, fetch_payloads: bool = True
    ) -> Optional[OrchestrationState]:
        req = pb.GetInstanceRequest(instanceId=instance_id, getInputsAndOutputs=fetch_payloads)
        res: pb.GetInstanceResponse = await self._stub.GetInstance(req)
        return new_orchestration_state(req.instanceId, res)

    async def wait_for_orchestration_start(
        self, instance_id: str, *, fetch_payloads: bool = False, timeout: int = 0
    ) -> Optional[OrchestrationState]:
        req = pb.GetInstanceRequest(instanceId=instance_id, getInputsAndOutputs=fetch_payloads)
        try:
            grpc_timeout = None if timeout == 0 else timeout
            self._logger.info(
                f"Waiting {'indefinitely' if timeout == 0 else f'up to {timeout}s'} for instance '{instance_id}' to start."
            )
            res: pb.GetInstanceResponse = await self._stub.WaitForInstanceStart(
                req, timeout=grpc_timeout
            )
            return new_orchestration_state(req.instanceId, res)
        except grpc.RpcError as rpc_error:
            if rpc_error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:  # type: ignore
                # Replace gRPC error with the built-in TimeoutError
                raise TimeoutError("Timed-out waiting for the orchestration to start")
            else:
                raise

    async def wait_for_orchestration_completion(
        self, instance_id: str, *, fetch_payloads: bool = True, timeout: int = 0
    ) -> Optional[OrchestrationState]:
        req = pb.GetInstanceRequest(instanceId=instance_id, getInputsAndOutputs=fetch_payloads)
        try:
            grpc_timeout = None if timeout == 0 else timeout
            self._logger.info(
                f"Waiting {'indefinitely' if timeout == 0 else f'up to {timeout}s'} for instance '{instance_id}' to complete."
            )
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
        except grpc.RpcError as rpc_error:
            if rpc_error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:  # type: ignore
                # Replace gRPC error with the built-in TimeoutError
                raise TimeoutError("Timed-out waiting for the orchestration to complete")
            else:
                raise

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
