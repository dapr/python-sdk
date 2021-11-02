---
type: docs
title: "Dapr Python SDK integration with FastAPI"
linkTitle: "FastAPI"
weight: 200000
description: How to create Dapr Python virtual actors with the FastAPI extension
---

The Dapr Python SDK provides integration with FastAPI using the `dapr-ext-fastapi` module

## Installation

You can download and install the Dapr FastAPI extension module with:

{{< tabs Stable Development>}}

{{% codetab %}}
```bash
pip install dapr-ext-fastapi
```
{{% /codetab %}}

{{% codetab %}}
{{% alert title="Note" color="warning" %}}
The development package will contain features and behavior that will be compatible with the pre-release version of the Dapr runtime. Make sure to uninstall any stable versions of the Python SDK extension before installing the dapr-dev package.
{{% /alert %}}

```bash
pip install dapr-ext-fastapi-dev
```
{{% /codetab %}}

{{< /tabs >}}

## Example

### Subscribing to an event

```python
from fastapi import FastAPI
from dapr.ext.fastapi import DaprApp


app = FastAPI()
dapr_app = DaprApp(app)


@dapr_app.subscribe(pubsub='pubsub', topic='some_topic')
def event_handler(event_data):
    print(event_data)
```

### Creating an actor

```python
from fastapi import FastAPI
from dapr.ext.fastapi import DaprActor
from demo_actor import DemoActor

app = FastAPI(title=f'{DemoActor.__name__}Service')

# Add Dapr Actor Extension
actor = DaprActor(app)

@app.on_event("startup")
async def startup_event():
    # Register DemoActor
    await actor.register_actor(DemoActor)

@app.get("/GetMyData")
def get_my_data():
    return "{'message': 'myData'}"
```