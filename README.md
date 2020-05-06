# Dapr SDK for Python

> WIP - Dapr core team does not have the official plan to support python-sdk now, except for the auto-generated gRPC client. but we're always welcoming any contribution.

## Structure of Python SDK

* [dapr/actor](./dapr/actor): Actor Framework
* [dapr/clients](./dapr/clients): HTTP clients for Dapr building blocks
* [dapr/serializers](./dapr/serializers): serializer/deserializer
* [dapr/conf](./dapr/conf): Configuration
* [flask_dapr](./flask_dapr): flask extension for Dapr
* [tests](./tests/): unit-tests
* [examples/demo_actor](./examples/demo_actor): demo actor example

## Status

* [x] Initial implementation of Actor Runtime/Manager/Proxy
* [x] Actor service invocation
* [x] RPC style actor proxy
* [x] Flask integration for Dapr Actor Service
* [x] Example for Actor service invocation
* [x] Complete tox.ini setup
* [x] Actor state management
* [ ] Actor timer
* [ ] Actor reminder
* [ ] Handle Error properly
* [ ] Package Dapr Actor SDK
* [ ] Create gRPC and HTTP rest clients for Dapr
* [ ] Flask extensions for Dapr State/Pubsub/Bindings
* [ ] Package Dapr SDK

## Developing

### Prerequisites

* [Install Dapr standalone mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-standalone)
* [Install Python 3.8+](https://www.python.org/downloads/)

### Build and test

1. Clone python-sdk
```bash
git clone https://github.com/dapr/python-sdk.git
cd python-sdk
```
2. Set PYTHONPATH environment
```bash
export PYTHONPATH=`pwd`
```
3. Run unit-test
```bash
tox -e py38
```

## Examples

* [DemoActor](./examples/demo_actor)