import asyncio
import logging

import grpc
import helloworld_service_pb2_grpc
from helloworld_service_pb2 import HelloRequest, HelloReply
import json, time


async def run() -> None:
    async with grpc.aio.insecure_channel('127.0.0.1:50007') as channel:
        metadata = (('dapr-app-id', 'invoke-receiver'),)
        stub = helloworld_service_pb2_grpc.HelloWorldServiceStub(channel)
        response = await stub.SayHello(request=HelloRequest(name='you'), metadata=metadata)
    print('Greeter client received: ' + response.message)


if __name__ == '__main__':
    print('I am in main')
    logging.basicConfig()
    asyncio.run(run())
