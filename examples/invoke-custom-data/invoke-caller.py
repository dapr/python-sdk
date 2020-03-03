import os

import grpc
import dapr_pb2 as dapr_messages
import dapr_pb2_grpc as dapr_services

import proto.response_pb2 as response_messages

from google.protobuf.any_pb2 import Any

# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Invoke the Receiver
data = Any(value='SOME_DATA'.encode('utf-8'))
response = client.InvokeService(dapr_messages.InvokeServiceEnvelope(id="invoke-receiver", method="my_method", data=data))

# Unpack the response
res = response_messages.CustomResponse()
response.data.type_url = "type.googleapis.com/CustomResponse"
response.data.Unpack(res)

# Print Result
print(res)

channel.close()