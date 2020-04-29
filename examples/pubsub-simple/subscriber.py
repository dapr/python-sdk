import os
from concurrent import futures
import time

import grpc
import dapr_pb2_grpc as dapr_services
import daprclient_pb2 as daprclient_messages
import daprclient_pb2_grpc as daprclient_services

from google.protobuf import empty_pb2

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# Start a gRPC client
port = os.getenv('DAPR_GRPC_PORT')
channel = grpc.insecure_channel(f"localhost:{port}")
client = dapr_services.DaprStub(channel)
print(f"Started gRPC client on DAPR_GRPC_PORT: {port}")


# Our server methods
class DaprClientServicer(daprclient_services.DaprClientServicer):
    def GetTopicSubscriptions(self, request, context):
        # Dapr will call this method to get the list of topics the app
        # wants to subscribe to. In this example, we are telling Dapr
        # To subscribe to a topic named TOPIC_A
        return daprclient_messages.GetTopicSubscriptionsEnvelope(topics=['TOPIC_A'])

    def OnTopicEvent(self, request, context):
        logging.info("Event received!!")
        return empty_pb2.Empty()


# Create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
daprclient_services.add_DaprClientServicer_to_server(
    DaprClientServicer(), server)

# Start the gRPC server
print('Starting server. Listening on port 50051.')
server.add_insecure_port('[::]:50051')
server.start()

# Since server.start() doesn't block, we need to do a sleep loop
try:
    while True:
        time.sleep(86400)
except KeyboardInterrupt:
    server.stop(0)
