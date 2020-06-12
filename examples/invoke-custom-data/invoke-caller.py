import os

import grpc

from dapr.proto import api_v1, api_service_v1, common_v1

import proto.response_pb2 as response_messages

from google.protobuf.any_pb2 import Any

# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = api_service_v1.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Invoke the Receiver

req = api_v1.InvokeServiceRequest(
    id="invoke-receiver",
    message=common_v1.InvokeRequest(
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