import os

import grpc

from dapr.proto.common.v1 import common_pb2 as commonv1pb
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services

import proto.response_pb2 as response_messages

from google.protobuf.any_pb2 import Any

# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Invoke the Receiver

req = dapr_messages.InvokeServiceRequest(
    id="invoke-receiver",
    message=commonv1pb.InvokeRequest(
        method='my_method',
        data=Any(value='SOME_DATA'.encode('utf-8')),
        content_type="text/plain; charset=UTF-8")
)
response = client.InvokeService(req)

# Unpack the response
res = response_messages.CustomResponse()
if response.data.Is(response_messages.CustomResponse.DESCRIPTOR):
    response.data.Unpack(res)
    print("test", flush=True)

# Print Result
print(res, flush=True)

channel.close()