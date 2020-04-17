import os
from concurrent import futures
import time

import grpc
import dapr_pb2 as dapr_messages
import dapr_pb2_grpc as dapr_services
import daprclient_pb2 as daprclient_messages
import daprclient_pb2_grpc as daprclient_services

from google.protobuf.any_pb2 import Any

# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Our server methods
class DaprClientServicer(daprclient_services.DaprClientServicer):
    def OnInvoke(self, request, context):
        response = ""

        if request.method == 'my_method':
            response = Any(value='INVOKE_RECEIVED'.encode('utf-8'))
        else:
            response = Any(value='METHOD_NOT_SUPPORTED'.encode('utf-8'))

        return response

        # Return response to caller
        return response

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