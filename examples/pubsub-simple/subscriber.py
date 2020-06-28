from cloudevents.sdk.event import v1
from dapr import App

app = App()

@app.subscriber(topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    print(event.Data(),flush=True)

app.daprize()
app.wait_until_stop()
