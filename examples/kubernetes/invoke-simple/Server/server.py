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

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

APP_PORT_GRPC  = os.getenv('APP_GRPC_PORT',  50050) # Note: this we need to expose in .yaml through dapr.io/app-port
DAPR_PORT_HTTP = os.getenv('DAPR_HTTP_PORT', 3500)
DAPR_PORT_GRPC = os.getenv('DAPR_GRPC_PORT', 50001) # Note: currently 50001 is always default

logger.info(f"==================================================")
logger.info(f"DAPR_PORT_GRPC: {DAPR_PORT_GRPC}; DAPR_PORT_HTTP: {DAPR_PORT_HTTP}")
logger.info(f"APP_PORT_GRPC: {APP_PORT_GRPC}")
logger.info(f"==================================================")

# Start a gRPC client
channel = grpc.insecure_channel(f"localhost:{DAPR_PORT_GRPC}")
client = dapr_services.DaprStub(channel)
logger.info(f"Started Dapr Gateway client on DAPR_GRPC_PORT: {DAPR_PORT_GRPC}")

# Our server methods
class DaprClientServicer(daprclient_services.DaprClientServicer):
    def OnInvoke(self, request, context):
        data = None
        content_type = ""

        logger.info("================== REQUEST ==================")
        logger.info(f"Content Type: {request.content_type}")
        logger.info(f"Message: {request.data.value}")

        if request.method == 'my_method':
            data = Any(value='SMSG_INVOKE_REQUEST'.encode('utf-8'))
            content_type = "text/plain; charset=UTF-8"
        else:
            data = Any(value='METHOD_NOT_SUPPORTED'.encode('utf-8'))
            content_type = "text/plain; charset=UTF-8"

        return commonv1pb.InvokeResponse(data=data, content_type=content_type)

# Create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
daprclient_services.add_DaprClientServicer_to_server(DaprClientServicer(), server)

# Start the gRPC server
server.add_insecure_port(f'[::]:{APP_PORT_GRPC}')
server.start() # It doesn't block
logger.info(f"Started Server on APP_PORT_GRPC: {APP_PORT_GRPC}")

# Since server.start() doesn't block, we need to do a sleep loop
try:
    while True:
        time.sleep(86400)
except KeyboardInterrupt:
    server.stop(0)