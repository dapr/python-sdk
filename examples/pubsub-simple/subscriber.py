import os
from concurrent import futures
import time

import grpc
from dapr.proto import appcallback_v1, appcallback_service_v1, common_v1

from google.protobuf import empty_pb2

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# Our server methods
class AppCallback(appcallback_service_v1.AppCallbackServicer):
    def ListTopicSubscriptions(self, request, context):
        # Dapr will call this method to get the list of topics the app
        # wants to subscribe to. In this example, we are telling Dapr
        # To subscribe to a topic named TOPIC_A
        return appcallback_v1.ListTopicSubscriptionsResponse(subscriptions=[appcallback_v1.TopicSubscription(topic='TOPIC_A'),])

    def OnTopicEvent(self, request, context):
        logging.info("Topic: " + request.topic)
        logging.info("Data content type: " + str(request.data_content_type))
        logging.info("Data: " + str(request.data))
        logging.info("Event received!!")
        return empty_pb2.Empty()


# Create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
appcallback_service_v1.add_AppCallbackServicer_to_server(AppCallback(), server)

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
