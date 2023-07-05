---
type: docs
title: "Dapr Python SDK"
linkTitle: "Python"
weight: 1000
description: Python SDK packages for developing Dapr applications
no_list: true
---

Dapr offers a variety of packages to help with the development of Python applications. Using them you can create Python clients, servers, and virtual actors with Dapr.

## Prerequisites

- [Dapr CLI]({{< ref install-dapr-cli.md >}}) installed
- Initialized [Dapr environment]({{< ref install-dapr-selfhost.md >}})
- [Python 3.7+](https://www.python.org/downloads/) installed

## Installation

To get started with the Python SDK, install the Dapr Python SDK package

{{< tabs Stable Development>}}

{{% codetab %}}
<!--stable-->
```bash
pip install dapr
```
{{% /codetab %}}

{{% codetab %}}
<!--dev-->
> **Note:** The development package will contain features and behavior that will be compatible with the pre-release version of the Dapr runtime. Make sure to uninstall any stable versions of the Python SDK before installing the dapr-dev package.
{{% /alert %}}

```bash
pip install dapr-dev
```

{{% /codetab %}}

{{< /tabs >}}


## Try it out

Clone the Python SDK repo.

```bash
git clone https://github.com/dapr/python-sdk.git
```

Walk through the Python quickstarts, tutorials, and examples to see Dapr in action:

| SDK samples | Description |
| ----------- | ----------- |
| [Quickstarts]({{< ref quickstarts >}}) | Experience Dapr's API building blocks in just a few minutes using the Python SDK. |
| [SDK samples](https://github.com/dapr/python-sdk/tree/master/examples) | Clone the SDK repo to try out some examples and get started. |
| [Bindings tutorial](https://github.com/dapr/quickstarts/tree/master/tutorials/bindings) | See how Dapr Python SDK works alongside other Dapr SDKs to enable bindings. |
| [Distributed Calculator tutorial](https://github.com/dapr/quickstarts/tree/master/tutorials/distributed-calculator/python) | Use the Dapr Python SDK to handle method invocation and state persistent capabilities. |
| [Hello World tutorial](https://github.com/dapr/quickstarts/tree/master/tutorials/hello-world) | Learn how to get Dapr up and running locally on your machine with the Python SDK. |
| [Hello Kubernetes tutorial](https://github.com/dapr/quickstarts/tree/master/tutorials/hello-kubernetes) | Get up and running with the Dapr Python SDK in a Kubernetes cluster. |
| [Observability tutorial](https://github.com/dapr/quickstarts/tree/master/tutorials/observability) | Explore Dapr's metric collection, tracing, logging and health check capabilities using the Python SDK. |
| [Pub/sub tutorial](https://github.com/dapr/quickstarts/tree/master/tutorials/pub-sub) | See how Dapr Python SDK works alongside other Dapr SDKs to enable pub/sub applications. |


## Available packages

<div class="card-deck">
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><b>Client</b></h5>
      <p class="card-text">Write Python applications to interact with a Dapr sidecar and other Dapr applications.</p>
      <a href="{{< ref python-client >}}" class="stretched-link"></a>
    </div>
  </div>
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><b>Actors</b></h5>
      <p class="card-text">Create and interact with stateful virtual actors in Python.</p>
      <a href="{{< ref python-actor >}}" class="stretched-link"></a>
    </div>
  </div>
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><b>Extensions</b></h5>
      <p class="card-text">Add Dapr capabilities to other Python frameworks using the gRPC extension, the FastAPI extension, or the Flask extension.</p>
      <a href="{{< ref python-sdk-extensions >}}" class="stretched-link"></a>
    </div>
  </div>
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><b>Workflow</b></h5>
      <p class="card-text">Create and manage workflows that work with other Dapr APIs in Python.</p>
      <a href="{{< ref python-workflow >}}" class="stretched-link"></a>
    </div>
  </div>
</div>

## More information

<div class="card-deck">
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><b>Serialization</b></h5>
      <p class="card-text">Learn more about serialization in Dapr SDKs.</p>
      <a href="{{< ref sdk-serialization >}}" class="stretched-link"></a>
    </div>
  </div>
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><b>PyPI</b></h5>
      <p class="card-text">Python Package Index</p>
      <a href="https://pypi.org/user/dapr.io/" class="stretched-link"></a>
    </div>
  </div>
</div>