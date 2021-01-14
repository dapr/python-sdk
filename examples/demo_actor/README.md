# DemoActor

This document describes how to create an Actor(DemoActor) and invoke its methods on the client application.

* **The actor interface(demo_actor_interface.py).** This contains the interface definition for the actor. Actor interfaces can be defined with any name. The interface defines the actor contract that is shared by the actor implementation and the clients calling the actor. Because client may depend on it, it typically makes sense to define it in an assembly that is separate from the actor implementation.

* **The actor service(demo_actor_service.py).** This implements FastAPI service that is going to host the actor. It contains the implementation of the actor, `demo_actor.py`. An actor implementation is a class that derives from the base type `Actor` and implements the interfaces defined in `demo_actor_interface.py`.

* **The actor service for flask(demo_actor_flask.py).** This implements Flask web service that is going to host the actor.

* **The actor client(demo_actor_client.py)** This contains the implementation of the actor client which calls DemoActor's method defined in Actor Interfaces.

## Prerequisites

* [Install Dapr standalone mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-standalone)
* [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr SDK

You can install dapr SDK package using pip command:

```sh
pip3 install -r ./demo_actor/requirements.txt
```

Or, you can use the current repo:

```sh
cd <repo root>
pip3 install -r ./dev-requirement.txt
export PYTHONPATH=`pwd`
```

## Run DemoActor on the local machine

1. Run Demo Actor service in new terminal window

```bash
$ cd ./demo_actor
$ dapr run --app-id demo-actor --app-port 3000 -- uvicorn --port 3000 demo_actor_service:app
...
== APP == Activate DemoActor actor!
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "POST /actors/DemoActor/1 HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/SetMyData HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
...
```

2. Run Demo client in new terminal window

```bash
$ cd ./demo_actor
# Run actor client
$ dapr run --app-id demo-client python3 demo_actor_client.py
...
== APP == call actor method via proxy.invoke_method()

== APP == b'null'

== APP == call actor method using rpc style

== APP == None

== APP == call SetMyData actor method to save the state

== APP == call GetMyData actor method to get the state

== APP == {'data': 'new_data', 'ts': datetime.datetime(2020, 11, 13, 0, 38, 36, 163000, tzinfo=tzutc())}

== APP == Register reminder

== APP == Register timer

== APP == waiting for 30 seconds...
```

## Run DemoActor on Kubernetes

1. Build and push docker image

```
$ cd examples/demo_actor/demo_actor
$ docker build -t [docker registry]/demo_actor:latest .
$ docker push [docker registry]/demo_actor:latest
$ cd ..
```

> For example, [docker registry] is docker hub account.

2. Follow [these steps](https://docs.dapr.io/getting-started/configure-redis/) to create a Redis store.

3. Once your store is created,  confirm validate `redis.yml` file in the `deploy` directory. 
    > **Note:** the `redis.yml` uses the secret created by `bitmany/redis` Helm chat to securely inject the password.

4. Apply the `redis.yml` file: `kubectl apply -f ./deploy/redis.yml` and observe that your state store was successfully configured!

```bash
component.dapr.io/statestore configured
```

5. Update docker image location in `./deploy/demo_actor_client.yml` and `./deploy/demo_actor_service.yml`

6. Deploy actor service and clients

```
cd deploy
kubectl apply -f ./deploy/demo_actor_service.yml
kubectl apply -f ./deploy/demo_actor_client.yml
```

7. See logs for actor service and client

Logs for actor service sidecar:
```
dapr  logs -a demoactor -k
```

Logs for actor service app:
```
kubectl logs -l app="demoactor" -c demoactor
```

Logs for actor client sidecar:
```
dapr  logs -a demoactor-client -k
```

Logs for actor service app:
```
kubectl logs -l app="demoactor-client" -c demoactor-client
```

