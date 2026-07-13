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

Shared helpers for actor-over-gRPC end-to-end tests.
"""

import grpc

from dapr.proto import api_service_v1, api_v1

PROBE_TIMEOUT_SECONDS = 10.0


def actor_stream_supported(grpc_port: int, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    """Probes daprd for working SubscribeActorEventsAlpha1 support.

    Only a registration ack counts as support. Sidecars that predate the RPC
    don't fail with UNIMPLEMENTED: the unknown method falls into daprd's gRPC
    proxy chain, which rejects it with UNKNOWN ("required metadata
    dapr-callee-app-id or dapr-app-id not found").

    The read is bounded by ``timeout`` so the probe can't hang CI when daprd
    never responds (wrong port, sidecar not ready); a timeout reads as
    unsupported.
    """
    channel = grpc.insecure_channel(f'localhost:{grpc_port}')
    stub = api_service_v1.DaprStub(channel)
    initial = api_v1.SubscribeActorEventsRequestAlpha1(
        initial_request=api_v1.SubscribeActorEventsRequestInitialAlpha1()
    )
    call = stub.SubscribeActorEventsAlpha1(iter([initial]), timeout=timeout)
    try:
        ack = next(call)
        return ack.HasField('initial_response')
    except (grpc.RpcError, StopIteration):
        return False
    finally:
        call.cancel()
        channel.close()
