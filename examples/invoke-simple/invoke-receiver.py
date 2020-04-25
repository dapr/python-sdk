import os
from concurrent import futures
import time

import grpc
from dapr.proto.common.v1 import common_pb2 as commonv1pb
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services
from dapr.proto.daprclient.v1 import daprclient_pb2 as daprclient_messages
from dapr.proto.daprclient.v1 import daprclient_pb2_grpc as daprclient_services

from google.protobuf.any_pb2 import Any

# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Our server methods
class DaprClientServicer(daprclient_services.DaprClientServicer):
    def OnInvoke(self, request, context):
        resp_data = Any()
        if request.method == 'my-method':
            resp_data.Pack(commonv1pb.DataWithContentType(
                content_type="text/plain; charset=UTF-8",
                body='INVOKE_RECEIVED'.encode('utf-8')
            ))
        else:
            resp_data.Pack(commonv1pb.DataWithContentType(
                content_type="text/plain; charset=UTF-8",
                body='unsupported methods'.encode('utf-8')
            ))

        # Return response to caller
        return commonv1pb.InvokeResponse(data=resp_data)

# Create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
daprclient_services.add_DaprClientServicer_to_server(DaprClientServicer(), server)

# Start the gRPC server
print('Starting server. Listening on port 50051.')
server.add_insecure_port('[::]:50051')
server.start()

# Since server.start() doesn't block, we need to do a sleep loop
try:
    while True:
        time.sleep(86400)
except KeyboardInterrupt:
    server.stop(0)