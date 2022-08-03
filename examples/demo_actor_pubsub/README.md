# Example - Dapr Virtual Actors Pubsub

This document describes how to create two actors and a service that has configured Pubsub to subscribe the actors to a topic and recieve events.

- **The actor interface(pubsub_actor_interface.py).** This contains the interface definition for the actor. Actor interfaces can be defined with any name. The interface defines the actor contract that is shared by the actor implementation and the clients calling the actor. Because client may depend on it, it typically makes sense to define it in an assembly that is separate from the actor implementation.
- **The actor service(pubsub_actor_service.py).** This implements FastAPI service that is going to host the actor. It contains the implementation of the actors declared in `pubsub_actor.py`. An actor implementation is a class that derives from the base type `Actor` and implements the interfaces defined in `pubsub_actor_interface.py`. 
- **The actor publisher(pubsub_actor_publisher.py)** This contains a service that publishes data to a specific topic using pubsub_actor_publish request.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)


## Run in self-hosted mode

1. Run Pubsub Actor service in new terminal window

<!-- STEP
name: Actor Service
background: true
sleep: 20
expected_stdout_lines:
  - '== APP == Activate DemoActor actor!'
  - '== APP == Method called with pubsub'
  - "== APP == Data received: {'id': '1', 'message': 'Hello 1 times'}"
  - '== APP == Method called with pubsub'
  - "== APP == Data received: {'id': '2', 'message': 'Hello 2 times'}"
  - '== APP == Activate AnotherActor actor!'
  - '== APP == This is another method called with pubsub for Actor: AnotherActor'
  - "== APP == Data received: {'id': '3', 'message': 'Hello 3 times'}"
  - '== APP == This is another method called with pubsub for Actor: AnotherActor'
  - "== APP == Data received: {'id': '4', 'message': 'Hello 4 times'}"
  - '== APP == Activate DemoActor actor!'
  - '== APP == This is another method called with pubsub for Actor: Demo Actor'
  - "== APP == Data received: {'id': '5', 'message': 'Hello 5 times'}"

-->

   ```bash
   dapr run --app-id pubsub-actor-service --app-port 3000 --dapr-http-port 3501 -- uvicorn --port 3000 pubsub_actor_service:app
   ```

<!-- END_STEP -->

2. Run Pubsub Actor Publisher in new terminal window

<!-- STEP
name: Actor Service
background: true
sleep: 15
expected_stdout_lines:
  - "== APP == {'id': '1', 'message': 'Hello 1 times'}"
  - "== APP == {'id': '2', 'message': 'Hello 2 times'}"
  - "== APP == {'id': '3', 'message': 'Hello 3 times'}"
  - "== APP == {'id': '4', 'message': 'Hello 4 times'}"
  - "== APP == {'id': '5', 'message': 'Hello 5 times'}"

-->

   ```bash
   # Run actor client
   dapr run --app-id demo-client python3 pubsub_actor_publisher.py
   ```

   Expected output:
   ```
   ...
   == APP == {'id': '1', 'message': 'Hello 1 times'}
   == APP == {'id': '2', 'message': 'Hello 2 times'}
   == APP == {'id': '3', 'message': 'Hello 3 times'}
   == APP == {'id': '4', 'message': 'Hello 4 times'}
   == APP == {'id': '5', 'message': 'Hello 5 times'}
   == APP == pubsub_actor_publisher.py:30: UserWarning: The Publish Actor Event API is an Alpha version and is subject to change.
   == APP ==   resp = d.publish_actor_event(
   == APP == pubsub_actor_publisher.py:52: UserWarning: The Publish Actor Event API is an Alpha version and is subject to change.
   == APP ==   resp = d.publish_actor_event(
   == APP == pubsub_actor_publisher.py:73: UserWarning: The Publish Actor Event API is an Alpha version and is subject to change.
   == APP ==   resp = d.publish_actor_event(
   ```

<!-- END_STEP -->

## Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: pubsub-actor-service'
expected_stderr_lines:
name: Shutdown dapr
-->

```bash
dapr stop --app-id pubsub-actor-service
```

<!-- END_STEP -->
