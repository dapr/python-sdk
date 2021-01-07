---
type: docs
title: "Getting started with the Dapr Client Python SDK"
linkTitle: "Dapr client"
weight: 10000
description: How to get up and running with the Dapr Python SDK
---

## Pre-requisites

- [Dapr CLI]({{< ref install-dapr-cli.md >}})
- Initialized [Dapr environment]({{< ref install-dapr-selfhost.md >}})
- [Python 3.7+](https://www.python.org/downloads/)

## Step 1: Install Dapr SDK

{{< tabs Stable Development>}}

{{% codetab %}}
```bash
pip3 install dapr
```
{{% /codetab %}}

{{% codetab %}}
{{% alert title="Note" color="warning" %}}
The development package will contain features and behavior that will be compatible with the pre-release version of the Dapr runtime. Make sure to uninstall any stable versions of the Python SDK before installing the dapr-dev package.
{{% /alert %}}

```bash
pip3 install dapr-dev
```
{{% /codetab %}}

{{< /tabs >}}

## Step 2: Import the DaprClient package

The dapr package contains the `DaprClient` which will be used to create and use a client.

```python
from dapr.clients import DaprClient
```

## Step 3: Try some how-to guides

- [How-To: Save and get state]({{< ref howto-get-save-state.md >}})