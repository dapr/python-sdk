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

## Examples

### Invoke a service

For a full guide on service invocation visit [this guide]({{< ref howto-invoke-discover-services.md >}}).

```python 
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.invoke_service(id='service-to-invoke', method='method-to-invoke', data='{"message":"Hello World"}')
```

### Save & get application state

For a full list of state operations visit [this guide]({{< ref howto-get-save-state.md >}}).

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

### Publish messages

For a full list of state operations visit [this guide]({{< ref howto-publish-subscribe.md >}}).

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.publish_event(pubsub_name='pubsub', topic='TOPIC_A', data='{"message":"Hello World"}')
```

### Interact with output bindings

For a full guide on output bindings visit [this guide]({{< ref howto-bindings.md >}}).

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.invoke_binding(name='kafkaBinding', operation='create', data='{"message":"Hello World"}')
```

### Retrieve secrets

For a full guide on secrets visit [this guide]({{< ref howto-secrets.md >}}).

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.get_secret(store_name='localsecretstore', key='secretKey')
```
