"""A fake Dapr gRPC sidecar serving TLS that records the metadata each call carried."""

from concurrent import futures
from typing import List, Tuple

import grpc

from dapr.proto import api_service_v1, api_v1


class RecordingDaprServicer(api_service_v1.DaprServicer):
    """Serves GetMetadata, recording each call's metadata."""

    def __init__(self) -> None:
        self.received_metadata: List[Tuple[Tuple[str, str], ...]] = []

    def GetMetadata(self, request, context):  # noqa: N802 - grpc-generated method name
        self.received_metadata.append(tuple(context.invocation_metadata()))
        return api_v1.GetMetadataResponse(id='fake-app')


class FakeSecureGrpcServer:
    """A real, locally bound gRPC server serving TLS."""

    def __init__(
        self,
        servicer: api_service_v1.DaprServicer,
        *,
        server_certificate_chain: bytes,
        server_private_key: bytes,
    ) -> None:
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        api_service_v1.add_DaprServicer_to_server(servicer, self._server)
        credentials = grpc.ssl_server_credentials([(server_private_key, server_certificate_chain)])
        self._port = self._server.add_secure_port('localhost:0', credentials)
        self._server.start()

    @property
    def address(self) -> str:
        return f'localhost:{self._port}'

    def stop(self) -> None:
        self._server.stop(None).wait()
