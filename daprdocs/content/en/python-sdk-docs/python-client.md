---
type: docs
title: "Getting started with the Dapr client Python SDK"
linkTitle: "Client"
weight: 10000
description: How to get up and running with the Dapr Python SDK
---

The Dapr client package allows you to interact with other Dapr applications from a Python application.

## Pre-requisites

- [Dapr CLI]({{< ref install-dapr-cli.md >}}) installed
- Initialized [Dapr environment]({{< ref install-dapr-selfhost.md >}})
- [Python 3.7+](https://www.python.org/downloads/) installed
- [Dapr Python module]({{< ref "python#install-the0dapr-module" >}}) installed

## Import the client package

The dapr package contains the `DaprClient` which will be used to create and use a client.

```python
from dapr.clients import DaprClient
```

## Building blocks

The Python SDK allows you to interface with all of the [Dapr building blocks]({{< ref building-blocks >}}).

### Invoke a service

```python 
from dapr.clients import DaprClient

with DaprClient() as d:
    # invoke a method (gRPC or HTTP GET)    
    resp = d.invoke_method('service-to-invoke', 'method-to-invoke', data='{"message":"Hello World"}')

    # for other HTTP verbs the verb must be specified
    # invoke a 'POST' method (HTTP only)    
    resp = d.invoke_method('service-to-invoke', 'method-to-invoke', data='{"id":"100", "FirstName":"Value", "LastName":"Value"}', http_verb='post')
```

- For a full guide on service invocation visit [How-To: Invoke a service]({{< ref howto-invoke-discover-services.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/invoke-simple) for code samples and instructions to try out service invocation

### Save & get application state

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    # Save state
    d.save_state(store_name="statestore", key="key1", value="value1")

    # Get state
    data = d.get_state(store_name="statestore", key="key1").data

    # Delete state
    d.delete_state(store_name="statestore", key="key1")
```

- For a full list of state operations visit [How-To: Get & save state]({{< ref howto-get-save-state.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/state_store) for code samples and instructions to try out state management

### Query application state (Alpha)

```python
    from dapr import DaprClient

    query = '''
    {
        "filter": {
            "EQ": { "value.state": "CA" }
        },
        "sort": [
            {
                "key": "value.person.id",
                "order": "DESC"
            }
        ]
    }
    '''

    with DaprClient() as d:
        resp = d.query_state(
            store_name='state_store',
            query=query,
            states_metadata={"metakey": "metavalue"},  # optional
        )
```

- For a full list of state store query options visit [How-To: Query state]({{< ref howto-state-query-api.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/state_store_query) for code samples and instructions to try out state store querying.

### Publish & subscribe to messages

##### Publish messages

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.publish_event(pubsub_name='pubsub', topic='TOPIC_A', data='{"message":"Hello World"}')
```

##### Subscribe to messages

```python
from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
import json

app = App()

# Default subscription for a topic
@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Received: id={data["id"]}, message="{data ["message"]}"' 
          ' content_type="{event.content_type}"',flush=True)

# Specific handler using Pub/Sub routing
@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A',
               rule=Rule("event.type == \"important\"", 1))
def mytopic_important(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Received: id={data["id"]}, message="{data ["message"]}"' 
          ' content_type="{event.content_type}"',flush=True)
```

- For a full list of state operations visit [How-To: Publish & subscribe]({{< ref howto-publish-subscribe.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/pubsub-simple) for code samples and instructions to try out pub/sub

### Interact with output bindings

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.invoke_binding(name='kafkaBinding', operation='create', data='{"message":"Hello World"}')
```

- For a full guide on output bindings visit [How-To: Use bindings]({{< ref howto-bindings.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/invoke-binding) for code samples and instructions to try out output bindings

### Retrieve secrets

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.get_secret(store_name='localsecretstore', key='secretKey')
```

- For a full guide on secrets visit [How-To: Retrieve secrets]({{< ref howto-secrets.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/secret_store) for code samples and instructions to try out retrieving secrets

### Get configuration

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    # Get Configuration
    configuration = d.get_configuration(store_name='configurationstore', keys=['orderId'], config_metadata={})
```

- For a full list of state operations visit [How-To: Get & save state]({{< ref howto-manage-configuration.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/configuration) for code samples and instructions to try out state management

## Related links
- [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples)