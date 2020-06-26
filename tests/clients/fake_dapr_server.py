import grpc

from concurrent import futures
from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.proto import api_service_v1, common_v1


class FakeDaprSidecar(api_service_v1.DaprServicer):
    def __init__(self):
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        api_service_v1.add_DaprServicer_to_server(self, self._server)

    def start(self, port: int = 8080):
        self._server.add_insecure_port(f'[::]:{port}')
        self._server.start()

    def stop(self):
        self._server.stop(None)

    def InvokeService(self, request, context) -> common_v1.InvokeResponse:
        headers = ()
        trailers = ()

        for k, v in context.invocation_metadata():
            headers = headers + (('h' + k, v), )
            trailers = trailers + (('t' + k, v), )

        resp = GrpcAny()
        content_type = ''

        if request.message.method == 'bytes':
            resp.value = request.message.data.value
            content_type = request.message.content_type
        else:
            resp = request.message.data

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return common_v1.InvokeResponse(data=resp, content_type=content_type)
