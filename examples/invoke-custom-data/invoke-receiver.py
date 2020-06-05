import os
from concurrent import futures
import time

import grpc
from dapr.proto import api_v1, api_service_v1, appcallback_service_v1, common_v1

import proto.response_pb2 as response_messages

from google.protobuf.any_pb2 import Any

# Our server methods
class AppCallback(appcallback_service_v1.AppCallbackServicer):
    def OnInvoke(self, request, context):
        data=None
        content_type=""
        if request.method == 'my_method':
            custom_response = response_messages.CustomResponse(isSuccess=True, code=200, message="Hello World - Success!")
            data = Any()
            data.Pack(custom_response)
        else:
            data = Any(value='METHOD_NOT_SUPPORTED'.encode('utf-8'))
            content_type="text/plain"

        print(data, flush=True)
        print(content_type, flush=True)
        return common_v1.InvokeResponse(data=data, content_type=content_type)

# Create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
appcallback_service_v1.add_AppCallbackServicer_to_server(AppCallback(), server)

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