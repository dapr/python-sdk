from cloudevents.sdk.event import v1
from dapr.ext.grpc import App

import json

app = App()

@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Subscriber received: id={data["id"]}, message="{data["message"]}"',flush=True)

app.run(50051)
