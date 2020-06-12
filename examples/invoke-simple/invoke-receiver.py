import os
import time
import grpc

from concurrent import futures

from dapr.proto import appcallback_service_v1, common_v1
from google.protobuf.any_pb2 import Any

# Our server methods
class AppCallback(appcallback_service_v1.AppCallbackServicer):
    def OnInvoke(self, request, context):
        data=None
        content_type=""
        if request.method == 'my-method':
            data = Any(value='INVOKE_RECEIVED'.encode('utf-8'))
            content_type = "text/plain; charset=UTF-8"
        else:
            data = Any(value='unsupported methods'.encode('utf-8'))
            content_type = "text/plain; charset=UTF-8"

        # Return response to caller
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