# Dapr SDK

> WIP - Porting from [dotnet-sdk](https://github.com/dapr/dotnet-sdk) to python
> 
> Dapr core team does not have the official plan to support the equivalent features of dotnet/java sdks, except for the auto-generated gRPC client. but we're always welcoming any contribution.

## Structures of Python SDK

* [dapr/actor](../dapr/actor): Actor Framework
* [dapr/clients](../dapr/clients): HTTP clients for Dapr building blocks (maybe we need to merge gRPC proto client to this directory)
* [dapr/serializers](../dapr/serializers): serializer/deserializer
* [dapr/conf](../dapr/conf): Configuration
* [flask_dapr](../flask_dapr): flask extension for Dapr
* [tests](../tests/): unit-tests
* [examples/demo_actor](../examples/demo_actor): demo actor example

## Status

* [x] Initial implementation of Actor Runtime/Manager/Proxy
* [x] Actor service invocation
* [x] RPC style actor proxy
* [x] Flask integration for Dapr Actor Service
* [x] Example for Actor service invocation
* [ ] Complete tox.ini setup
* [ ] Actor state management
* [ ] Actor timer
* [ ] Actor reminder
* [ ] Package Dapr Actor SDK
* [ ] Create gRPC and HTTP rest clients for Dapr
* [ ] Flask extensions for Dapr State/Pubsub/Bindings
* [ ] Package Dapr SDK

## Developing

### Prerequisites

* [Install Dapr standalone mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-standalone)
* [Install Python 3.7+](https://www.python.org/downloads/)

### Build and test

1. Clone python-sdk
```bash
git clone https://github.com/dapr/python-sdk.git
cd python-sdk
```
2. Install pythons libs for Dapr Python SDK
```bash
pip3 install -r ./tests/test-requirement.txt
```
3. Set PYTHONPATH environment
```bash
export PYTHONPATH=`pwd`
```
3. Run unit-test (later, we will use tox)
```bash
python3 -m unittest discover ./tests/
```

### Try DemoActor example

1. Run Demo Actor service in new terminal window
```bash
$ cd python-sdk
$ pip3 install -r ./tests/test-requirement.txt
$ export PYTHONPATH=`pwd`
$ cd examples/demo_actor/service
$ dapr run --app-id demo-actor --app-port 3000 python3 app.py
...
== APP ==  * Serving Flask app "DemoActorService" (lazy loading)
== APP ==  * Environment: production
== APP ==    WARNING: This is a development server. Do not use it in a production deployment.
== APP ==    Use a production WSGI server instead.
== APP ==  * Debug mode: off
== APP ==  * Running on http://127.0.0.1:3000/ (Press CTRL+C to quit)
== DAPR == time="2020-02-29T13:52:15-08:00" level=info msg="application discovered on port 3000"
== APP == 127.0.0.1 - - [29/Feb/2020 13:52:15] "GET /dapr/config HTTP/1.1" 200 -
...
== APP == Activate DemoActor actor!
== APP == 127.0.0.1 - - [29/Feb/2020 13:52:24] "POST /actors/DemoActor/1 HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [29/Feb/2020 13:52:24] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
...
```
2. Run Demo client in new terminal window
```bash
$ cd python-sdk
$ export PYTHONPATH=`pwd`
$ cd examples/demo_actor/client
# Run actor client
$ dapr run --app-id demo-client python3 demo_actor_client.py
...
== APP == {'data': 'default'}
...
```
