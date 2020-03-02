import os

import grpc
import dapr_pb2 as dapr_messages
import dapr_pb2_grpc as dapr_services

from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

data = Any(value='ACTION=1'.encode('utf-8'))
response = client.InvokeService(dapr_messages.InvokeServiceEnvelope(id="invoke-receiver", method="my_method", data=data))
print(response.data.value)

channel.close()