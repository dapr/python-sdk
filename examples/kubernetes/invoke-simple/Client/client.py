import os

import grpc
import Proto.dapr_pb2 as dapr_messages
import Proto.dapr_pb2_grpc as dapr_services

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
logger.info(f"Started gRPC client on DAPR_GRPC_PORT: {DAPR_PORT_GRPC}")

data = Any(value='ACTION=1'.encode('utf-8'))
response = client.InvokeService(dapr_messages.InvokeServiceEnvelope(id="id-demo-grpc-server", method="my_method", data=data))
print(response.data.value)

channel.close()