import logging

import grpc
import helloworld_service_pb2_grpc
from helloworld_service_pb2 import HelloRequest, HelloReply
from dapr.ext.grpc import App
import json


class HelloWorldService(helloworld_service_pb2_grpc.HelloWorldService):
    def SayHello(self, request: HelloRequest, context: grpc.aio.ServicerContext) -> HelloReply:
        logging.info(request)
        return HelloReply(message='Hello, %s!' % request.name)


app = App()

if __name__ == '__main__':
    print('starting the HelloWorld Service')
    logging.basicConfig(level=logging.INFO)
    app.add_external_service(
        helloworld_service_pb2_grpc.add_HelloWorldServiceServicer_to_server, HelloWorldService()
    )
    app.run(50051)
