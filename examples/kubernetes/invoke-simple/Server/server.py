import os
from concurrent import futures
import time

import grpc
import Proto.dapr_pb2 as dapr_messages
import Proto.dapr_pb2_grpc as dapr_services
import Proto.daprclient_pb2 as daprclient_messages
import Proto.daprclient_pb2_grpc as daprclient_services

from google.protobuf.any_pb2 import Any

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

APP_PORT_GRPC  = os.getenv('APP_GRPC_PORT',  50050) # Note: this we need to expose in .yaml through dapr.io/port
DAPR_PORT_HTTP = os.getenv('DAPR_HTTP_PORT', 3500)
DAPR_PORT_GRPC = os.getenv('DAPR_GRPC_PORT', 50001) # Note: currently 50001 is always default

logger.info(f"==================================================")
logger.info(f"DAPR_PORT_GRPC: {DAPR_PORT_GRPC}; DAPR_PORT_HTTP: {DAPR_PORT_HTTP}")
logger.info(f"APP_PORT_GRPC: {APP_PORT_GRPC}")
logger.info(f"==================================================")

# Start a gRPC client
channel = grpc.insecure_channel(f"localhost:{DAPR_PORT_GRPC}")
client = dapr_services.DaprStub(channel)
logger.info(f"Started gRPC client on DAPR_GRPC_PORT: {DAPR_PORT_GRPC}")

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
print(f'Starting server. Listening on port {APP_PORT_GRPC}.')
server.add_insecure_port(f'[::]:{APP_PORT_GRPC}')
server.start()

# Since server.start() doesn't block, we need to do a sleep loop
try:
    while True:
        time.sleep(86400)
except KeyboardInterrupt:
    server.stop(0)