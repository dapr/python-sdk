---
type: docs
title: "Getting started with the Dapr actor Python SDK"
linkTitle: "Actor"
weight: 20000
description: How to get up and running with the Dapr Python SDK
---

The Dapr actor package allows you to interact with Dapr virtual actors from a Python application.

## Pre-requisites

- [Dapr CLI]({{< ref install-dapr-cli.md >}}) installed
- Initialized [Dapr environment]({{< ref install-dapr-selfhost.md >}})
- [Python 3.7+](https://www.python.org/downloads/) installed
- [Dapr Python package]({{< ref "python#installation" >}}) installed

## Actor interface

The interface defines the actor contract that is shared between the actor implementation and the clients calling the actor. Because a client may depend on it, it typically makes sense to define it in an assembly that is separate from the actor implementation.

```python
from dapr.actor import ActorInterface, actormethod

class DemoActorInterface(ActorInterface):
    @actormethod(name="GetMyData")
    async def get_my_data(self) -> object:
        ...
```

## Actor services

An actor service hosts the virtual actor. It is implemented a class that derives from the base type `Actor` and implements the interfaces defined in the actor interface.

Actors can be created using one of the Dapr actor extensions:
   - [FastAPI actor extension]({{< ref python-fastapi.md >}})
   - [Flask actor extension]({{< ref python-flask.md >}})

## Actor client

An actor client contains the implementation of the actor client which calls the actor methods defined in the actor interface.

```python
import asyncio

from dapr.actor import ActorProxy, ActorId
from demo_actor_interface import DemoActorInterface

async def main():
    # Create proxy client
    proxy = ActorProxy.create('DemoActor', ActorId('1'), DemoActorInterface)

    # Call method on client
    resp = await proxy.GetMyData()
```

## Sample

Visit [this page](https://github.com/dapr/python-sdk/tree/release-1.0/examples/demo_actor) for a runnable actor sample.