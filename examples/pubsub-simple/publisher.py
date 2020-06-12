import os
import grpc

from dapr.proto import api_v1, api_service_v1
from google.protobuf.any_pb2 import Any


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = api_service_v1.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")

data = 'ACTION=1'.encode('utf-8')
# publishing a message to topic TOPIC_A
client.PublishEvent(api_v1.PublishEventRequest(
    topic='TOPIC_A', data=data))

print("Published!!")

channel.close()
