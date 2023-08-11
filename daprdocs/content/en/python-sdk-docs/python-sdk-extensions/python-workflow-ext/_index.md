---
type: docs
title: "Dapr Python SDK integration with Dapr Workflow extension"
linkTitle: "Dapr Workflow"
weight: 400000
description: How to get up and running with the Dapr Workflow extension
no_list: true
---

{{% alert title="Note" color="primary" %}}
Dapr Workflow is currently in alpha.
{{% /alert %}}

The Dapr Python SDK provides a built in Dapr Workflow extension, `dapr.ext.workflow`, for creating Dapr services.

## Installation

You can download and install the Dapr Workflow extension with:

{{< tabs Stable Development>}}

{{% codetab %}}
```bash
pip install dapr-ext-workflow
```
{{% /codetab %}}

{{% codetab %}}
{{% alert title="Note" color="warning" %}}
The development package will contain features and behavior that will be compatible with the pre-release version of the Dapr runtime. Make sure to uninstall any stable versions of the Python SDK extension before installing the `dapr-dev` package.
{{% /alert %}}

```bash
pip3 install dapr-ext-workflow-dev
```
{{% /codetab %}}

{{< /tabs >}}

## Next steps

{{< button text="Getting started with the Dapr Workflow Python SDK" page="python-workflow.md" >}}
