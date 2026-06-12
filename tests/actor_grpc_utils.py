"""Shared helpers for actor-over-gRPC end-to-end tests."""

import grpc

from dapr.proto import api_service_v1, api_v1


def actor_stream_supported(grpc_port: int) -> bool:
    """Probes daprd for working SubscribeActorEventsAlpha1 support.

    Only a registration ack counts as support. Sidecars that predate the RPC
    don't fail with UNIMPLEMENTED: the unknown method falls into daprd's gRPC
    proxy chain, which rejects it with UNKNOWN ("required metadata
    dapr-callee-app-id or dapr-app-id not found").
    """
    channel = grpc.insecure_channel(f'localhost:{grpc_port}')
    stub = api_service_v1.DaprStub(channel)
    initial = api_v1.SubscribeActorEventsRequestAlpha1(
        initial_request=api_v1.SubscribeActorEventsRequestInitialAlpha1()
    )
    call = stub.SubscribeActorEventsAlpha1(iter([initial]))
    try:
        ack = next(call)
        return ack.HasField('initial_response')
    except (grpc.RpcError, StopIteration):
        return False
    finally:
        call.cancel()
        channel.close()
