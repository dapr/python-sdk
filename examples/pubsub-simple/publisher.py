import os

import grpc
from dapr.proto.dapr.v1 import dapr_pb2 as dapr_messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as dapr_services

from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

data = Any(value='ACTION=1'.encode('utf-8'))
# publishing a message to topic TOPIC_A
client.PublishEvent(dapr_messages.PublishEventEnvelope(
    topic='TOPIC_A', data=data))

print("Published!!")

channel.close()
