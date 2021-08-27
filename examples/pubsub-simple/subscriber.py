from cloudevents.sdk.event import v1
from dapr.ext.grpc import App, Rule

import json

app = App()

@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A', rule=Rule("event.type == \"test\"", 0))
def mytopic(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Subscriber received: id={data["id"]}, message="{data["message"]}", content_type="{event.content_type}"',flush=True)

app.run(50051)
