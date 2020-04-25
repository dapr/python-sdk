import os

import grpc
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services
from dapr.proto.common.v1 import common_pb2

from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

data1=Any(value='ACTION=1'.encode('utf-8'))
message1 = common_pb2.InvokeRequest(method='my-method', data=data1)
response = client.InvokeService(dapr_messages.InvokeServiceRequest(id="invoke-receiver", message=message1))
print(response.data.value)

channel.close()