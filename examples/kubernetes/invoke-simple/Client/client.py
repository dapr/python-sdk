import os

import grpc
from dapr.proto.common.v1 import common_pb2 as commonv1pb
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services

from google.protobuf.any_pb2 import Any

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('MyLogger')

DAPR_PORT_HTTP = os.getenv('DAPR_HTTP_PORT', 3500)
DAPR_PORT_GRPC = os.getenv('DAPR_GRPC_PORT', 50001) # Note: currently 50001 is always default

logger.info(f"==================================================")
logger.info(f"DAPR_PORT_GRPC: {DAPR_PORT_GRPC}; DAPR_PORT_HTTP: {DAPR_PORT_HTTP}")
logger.info(f"==================================================")

# Start a gRPC client
channel = grpc.insecure_channel(f"localhost:{DAPR_PORT_GRPC}")
client = dapr_services.DaprStub(channel)
logger.info(f"Started Dapr Gateway client on DAPR_GRPC_PORT: {DAPR_PORT_GRPC}")

req = dapr_messages.InvokeServiceRequest(
  id = "id-demo-grpc-server", # As described in the demo-grpc-client.yaml pod description
  message = commonv1pb.InvokeRequest(
    method = "my_method",
    data = Any(value='CMSG_INVOKE_REQUEST'.encode('utf-8')),
    content_type="text/plain; charset=UTF-8"
  )
)

logger.info(f"Invoking Service")
res = client.InvokeService(req)
logger.info(f"Invoked Service")

# Print the response
logger.info("================== RESPONSE ==================")
logger.info(f"Content Type: {res.content_type}")
logger.info(f"Message: {res.data.value}")

channel.close()