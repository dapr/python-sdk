# Dapr SDK for Python

[![PyPI - Version](https://img.shields.io/pypi/v/dapr?style=flat&logo=pypi&logoColor=white&label=Latest%20version)](https://pypi.org/project/dapr/) 
[![PyPI - Downloads](https://img.shields.io/pypi/dm/dapr?style=flat&logo=pypi&logoColor=white&label=Downloads)](https://pypi.org/project/dapr/) 
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/dapr/python-sdk/.github%2Fworkflows%2Fbuild.yaml?branch=main&label=Build&logo=github)](https://github.com/dapr/python-sdk/actions/workflows/build.yaml) 
[![codecov](https://codecov.io/gh/dapr/python-sdk/branch/main/graph/badge.svg)](https://codecov.io/gh/dapr/python-sdk) 
[![GitHub License](https://img.shields.io/github/license/dapr/python-sdk?style=flat&label=License&logo=github)](https://github.com/dapr/python-sdk/blob/main/LICENSE) 
[![GitHub issue custom search in repo](https://img.shields.io/github/issues-search/dapr/python-sdk?query=type%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22&label=Good%20first%20issues&style=flat&logo=github)](https://github.com/dapr/python-sdk/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 
[![Discord](https://img.shields.io/discord/778680217417809931?label=Discord&style=flat&logo=discord)](http://bit.ly/dapr-discord) 
[![YouTube Channel Views](https://img.shields.io/youtube/channel/views/UCtpSQ9BLB_3EXdWAUQYwnRA?style=flat&label=YouTube%20views&logo=youtube)](https://youtube.com/@daprdev) 
<!-- IGNORE_LINKS -->
[![X (formerly Twitter) Follow](https://img.shields.io/twitter/follow/daprdev?logo=x&style=flat)](https://twitter.com/daprdev)
<!-- END_IGNORE -->

[Dapr](https://docs.dapr.io/concepts/overview/) is a portable, event-driven, serverless runtime for building distributed applications across cloud and edge.

Dapr SDK for Python allows you to implement the [Virtual Actor model](https://docs.dapr.io/developing-applications/building-blocks/actors/actors-overview/), based on the actor design pattern. This SDK can run locally, in a container and in any distributed systems environment.

This includes the following packages:

* [dapr.actor](./dapr/actor): Actor Framework
* [dapr.clients](./dapr/clients): Dapr clients for Dapr building blocks
* [dapr.conf](./dapr/conf): Configuration
* [dapr.serializers](./dapr/serializers): serializer/deserializer
* [dapr.proto](./dapr/proto): Dapr gRPC autogenerated gRPC clients
* [dapr.ext.grpc](./ext/dapr-ext-grpc): gRPC extension for Dapr
* [dapr.ext.fastapi](./ext/dapr-ext-fastapi): FastAPI extension (actor) for Dapr
* [flask.dapr](./ext/flask_dapr): Flask extension (actor) for Dapr

## Getting started

### Prerequisites

* [Install Dapr standalone mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted)
* [Install Python 3.9+](https://www.python.org/downloads/)

### Install Dapr python sdk

* Official package

```sh
# Install Dapr client sdk
pip3 install dapr

# Install Dapr gRPC AppCallback service extension
pip3 install dapr-ext-grpc

# Install Dapr Fast Api extension for Actor
pip3 install dapr-ext-fastapi
```

* Development package

```sh
# Install Dapr client sdk
pip3 install dapr-dev

# Install Dapr gRPC AppCallback service extension
pip3 install dapr-ext-grpc-dev

# Install Dapr Fast Api extension for Actor
pip3 install dapr-ext-fastapi-dev
```

> Note: Do not install both packages.

### Try out examples

Go to [Examples](./examples)

## Developing

### Build and test

1. Clone python-sdk

```bash
git clone https://github.com/dapr/python-sdk.git
cd python-sdk
```

2. Install a project in a editable mode

```bash
pip3 install -e .
pip3 install -e ./ext/dapr-ext-grpc/
pip3 install -e ./ext/dapr-ext-fastapi/
pip3 install -e ./ext/dapr-ext-workflow/
```

3. Install required packages

```bash
pip3 install -r dev-requirements.txt
```

4. Run linter

```bash
tox -e flake8
```

5. Run autofix

```bash
tox -e ruff
```

6. Run unit-test

```bash
tox -e py311
```

7. Run type check

```bash
tox -e type
```

8. Run examples

```bash
tox -e examples
```

## Documentation

Documentation is generated using Sphinx. Extensions used are mainly Napoleon (To process the Google Comment Style) and Autodocs (For automatically generating documentation). The `.rst` files are generated using Sphinx-Apidocs.

To generate documentation:

```bash
tox -e doc
```

The generated files will be found in `docs/_build`.

## Generate gRPC Protobuf client

```sh
pip3 install -r tools/requirements.txt
./tools/regen_grpcclient.sh
```

## Help & Feedback

Need help or have feedback on the SDK? Please open a GitHub issue or come chat with us in the `#python-sdk` channel of our Discord server ([click here to join](https://discord.gg/MySdVxrH)).

## Code of Conduct

This project follows the [CNCF Code of Conduct](https://github.com/cncf/foundation/blob/master/code-of-conduct.md).

