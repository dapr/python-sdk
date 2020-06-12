import os

import grpc

from dapr.proto import api_v1, api_service_v1, common_v1

from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = api_service_v1.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Create a typed message with content type and body
test_message = Any(value='INVOKE_RECEIVED'.encode('utf-8'))

# Invoke the method 'my-method' on receiver 
req = api_v1.InvokeServiceRequest(
    id="invoke-receiver",
    message=common_v1.InvokeRequest(
        method='my-method',
        data=test_message,
        content_type="text/plain; charset=UTF-8")
)
response = client.InvokeService(req)

# Print the response
print(response.content_type)
print(response.data.value)

channel.close()