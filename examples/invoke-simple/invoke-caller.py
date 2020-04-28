import os

import grpc

from dapr.proto.common.v1 import common_pb2 as commonv1pb
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services
from dapr.proto.common.v1 import common_pb2

from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

# Create a typed message with content type and body
test_message = Any()
test_message.Pack(commonv1pb.DataWithContentType(
    content_type="text/plain; charset=UTF-8",
    body='INVOKE_RECEIVED'.encode('utf-8')
))

# Invoke the method 'my-method' on receiver 
req = dapr_messages.InvokeServiceRequest(
    id="invoke-receiver",
    message=common_pb2.InvokeRequest(method='my-method', data=test_message)
)
response = client.InvokeService(req)

# Print the response
if response.data.Is(commonv1pb.DataWithContentType.DESCRIPTOR):
    resp_data = commonv1pb.DataWithContentType()
    response.data.Unpack(resp_data)
    print(resp_data.content_type)
    print(resp_data.body)

channel.close()