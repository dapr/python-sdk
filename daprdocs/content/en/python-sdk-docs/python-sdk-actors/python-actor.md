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
- [Python 3.8+](https://www.python.org/downloads/) installed
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


## Mock Actor Testing

The Dapr Python SDK provides the ability to create mock actors to unit test your actor methods and how they interact with the actor state.

### Sample Usage 


```
from dapr.actor.runtime.mock_actor import create_mock_actor

class MyActor(Actor, MyActorInterface):
    async def save_state(self, data) -> None:
        await self._state_manager.set_state('state', data)
        await self._state_manager.save_state()

mock_actor = create_mock_actor(MyActor, "id")

await mock_actor.save_state(5)
assert mockactor._state_manager._mock_state == 5 #True
```
Mock actors work by passing your actor class as well as the actor id (str) into the function create_mock_actor, which returns an instance of the actor with a bunch of the internal actor methods overwritten, such that instead of attempting to interact with Dapr to save state, manage timers, etc it instead only uses local variables.

Those variables are:
* **_state_manager._mock_state()**
A [str, object] dict where all the actor state is stored. Any variable saved via _state_manager.save_state(key, value), or any other statemanager method is stored in the dict as that key, value combo. Any value loaded via try_get_state or any other statemanager method is taken from this dict.

* **_state_manager._mock_timers()**
A [str, ActorTimerData] dict which holds the active actor timers. Any actor method which would add or remove a timer adds or pops the appropriate ActorTimerData object from this dict.

* **_state_manager._mock_reminders()**
A [str, ActorReminderData] dict which holds the active actor reminders. Any actor method which would add or remove a timer adds or pops the appropriate ActorReminderData object from this dict.

**Note: The timers and reminders will never actually trigger. The dictionaries exist only so methods that should add or remove timers/reminders can be tested. If you need to test the callbacks they should activate, you should call them directly with the appropriate values:**
```
result = await mock_actor.recieve_reminder(name, state, due_time, period, _ttl)
# Test the result directly or test for side effects (like changing state) by querying _state_manager._mock_state
```

### Usage and Limitations

**The \_on\_activate method will not be called automatically the way it is when Dapr initializes a new Actor instance. You should call it manually as needed as part of your tests.**

The \_\_init\_\_, register_timer, unregister_timer, register_reminder, unregister_reminder methods are all overwritten by the MockActor class that gets applied as a mixin via create_mock_actor. If your actor itself overwrites these methods, those modifications will themselves be overwritten and the actor will likely not behave as you expect.

*note: \_\_init\_\_ is a special case where you are expected to define it as*
```
    def __init__(self, ctx, actor_id):
        super().__init__(ctx, actor_id)
```
*Mock actors work fine with this, but if you have added any extra logic into \_\_init\_\_, it will be overwritten. It is worth noting that the correct way to apply logic on initialization is via \_on\_activate (which can also be safely used with mock actors) instead of \_\_init\_\_.*

The actor _runtime_ctx variable is set to None. Obviously all the normal actor methods have been overwritten such as to not call it, but if your code itself interacts directly with _runtime_ctx, it will likely break.

The actor _state_manager is overwritten with an instance of MockStateManager. This has all the same methods and functionality of the base ActorStateManager, except for using the various _mock variables for storing data instead of the _runtime_ctx. If your code implements its own custom state manager it will be overwritten and your code will likely break.

### Type Hinting

Because of Python's lack of a unified method for type hinting type intersections (see: [python/typing #213](https://github.com/python/typing/issues/213)), type hinting is unfortunately mostly broken with Mock Actors. The return type is type hinted as "instance of Actor subclass T" when it should really be type hinted as "instance of MockActor subclass T" or "instance of type intersection [Actor subclass T, MockActor]" (where, it is worth noting, MockActor is itself a subclass of Actor).

This means that, for example, if you hover over ```mockactor._state_manager``` in a code editor, it will come up as an instance of ActorStateManager (instead of MockStateManager), and various IDE helper functions (like VSCode's ```Go to Definition```, which will bring you to the definition of ActorStateManager instead of MockStateManager) won't work properly.

For now, this issue is unfixable, so it's merely something to be noted because of the confusion it might cause. If in the future it becomes possible to accurately type hint cases like this feel free to open an issue about implementing it.