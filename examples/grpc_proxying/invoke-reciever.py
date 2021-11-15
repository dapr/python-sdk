import asyncio
import logging

import grpc
import helloworld_service_pb2_grpc
from helloworld_service_pb2 import HelloRequest, HelloReply
from dapr.ext.grpc import App
from cloudevents.sdk.event import v1
import json

class HelloWorldService(helloworld_service_pb2_grpc.HelloWorldService):
    def SayHello(
            self, request: HelloRequest,
            context: grpc.aio.ServicerContext) -> HelloReply:
        print('hello in servicer')
        return HelloReply(message='Hello, %s!' % request.name)


# async def serve() -> None:
#     server = grpc.aio.server()
#     helloworld_service_pb2_grpc.add_HelloWorldServiceServicer_to_server(HelloWorldService(), server)
#     listen_addr = '127.0.0.1:50051'
#     server.add_insecure_port(listen_addr)
#     logging.info("Starting server on this: %s", listen_addr)
#     await server.start()
#     await server.wait_for_termination()
app = App()

@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Subscriber received: id={data["id"]}, message="{data["message"]}", content_type="{event.content_type}"',flush=True)


if __name__ == '__main__':
    print('starting the HelloWorld Service')
    logging.basicConfig(level=logging.INFO)
    # asyncio.run(serve())
    app.add_external_service(helloworld_service_pb2_grpc.add_HelloWorldServiceServicer_to_server, HelloWorldService())
    app.run(50051)