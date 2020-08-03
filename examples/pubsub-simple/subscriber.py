from cloudevents.sdk.event import v1
from dapr.ext.grpc import App

app = App()

@app.subscribe(topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    print(event.Data(),flush=True)

app.run(50051)
