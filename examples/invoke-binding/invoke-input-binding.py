import os
import time
import grpc

from concurrent import futures

from dapr.proto import appcallback_service_v1, appcallback_v1
from google.protobuf.any_pb2 import Any

# Our server methods


class AppCallback(appcallback_service_v1.AppCallbackServicer):
    def ListInputBindings(self, request, context):
        return appcallback_v1.ListInputBindingsResponse(bindings=['kafkaBinding'])

    def OnBindingEvent(self, request, context):
        print(request.name, flush=True)
        print(request.data, flush=True)

        # Return response to caller
        return appcallback_v1.BindingEventResponse(store_name='Non Persistant', to='nothing', data=request.data)


# Create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
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
