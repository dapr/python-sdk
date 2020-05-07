import os

import grpc

from dapr.proto.common.v1 import common_pb2 as commonv1pb
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services

from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Create a typed message with content type and body
test_message = Any(value='INVOKE_RECEIVED'.encode('utf-8'))

# Invoke the method 'my-method' on receiver 
req = dapr_messages.InvokeServiceRequest(
    id="invoke-receiver",
    message=commonv1pb.InvokeRequest(
        method='my-method',
        data=test_message,
        content_type="text/plain; charset=UTF-8")
)
response = client.InvokeService(req)

# Print the response
print(response.content_type)
print(response.data.value)

channel.close()