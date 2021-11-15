import asyncio
import logging

import grpc
import helloworld_service_pb2_grpc
from helloworld_service_pb2 import HelloRequest, HelloReply
from dapr.clients import DaprClient
import json, time

async def run() -> None:
    async with grpc.aio.insecure_channel('127.0.0.1:50007') as channel:
        metadata = (('dapr-app-id', 'server'),)
        stub = helloworld_service_pb2_grpc.HelloWorldServiceStub(channel)
        response = await stub.SayHello(request=HelloRequest(name='you'), metadata=metadata)
    print("Greeter client received: " + response.message)


def publish() -> None:
    with DaprClient() as d:
        id=0
        while True:
            id+=1
            req_data = {
                'id': id,
                'message': 'hello world'
            }

            # Create a typed message with content type and body
            resp = d.publish_event(
                pubsub_name='pubsub',
                topic_name='TOPIC_A',
                data=json.dumps(req_data),
                data_content_type='application/json',
            )

            # Print the request
            print(req_data, flush=True)
            time.sleep(2)


if __name__ == '__main__':
    print('I am in main')
    logging.basicConfig()
    asyncio.run(run())
    publish()
