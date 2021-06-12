---
type: docs
title: "Dapr Python SDK"
linkTitle: "Python"
weight: 1000
description: Python SDK packages for developing Dapr applications
no_list: true
---

Dapr offers a variety of packages to help with the development of Python applications. Using them you can create Python clients, servers, and virtual actors with Dapr.

## Available packages

- [**Dapr client**]({{< ref python-client.md >}}) for writing Python applications to interact with the Dapr sidecar and other Dapr applications
- [**Dapr actor**]({{< ref python-actor.md >}}) for creating and interacting with stateful virtual actors in Python
- [**Extensions**]({{< ref python-sdk-extensions >}}) for adding Dapr capabilities to other Python frameworks
    - [**gRPC extension**]({{< ref python-grpc.md >}}) for creating a gRPC server with Dapr
    - [**FastAPI extension**]({{< ref python-fastapi.md >}}) for adding Dapr actor capabilities to FastAPI applications
    - [**Flask extension**]({{< ref python-flask.md >}}) for adding Dapr actor capabilities to Flask applications

## Install the Dapr module

{{< tabs Stable Development>}}

{{% codetab %}}
```bash
pip install dapr
```
{{% /codetab %}}

{{% codetab %}}
{{% alert title="Note" color="warning" %}}
The development package will contain features and behavior that will be compatible with the pre-release version of the Dapr runtime. Make sure to uninstall any stable versions of the Python SDK before installing the dapr-dev package.
{{% /alert %}}

```bash
pip install dapr-dev
```
{{% /codetab %}}

{{< /tabs >}}

## Try it out

Clone the Python SDK repo to try out some of the [examples](https://github.com/dapr/python-sdk/tree/master/examples).

```bash
git clone https://github.com/dapr/python-sdk.git
```

## More information

- [Python Package Index (PyPI)](https://pypi.org/user/dapr.io/)
- [Dapr SDK serialization]({{< ref sdk-serialization.md >}})
