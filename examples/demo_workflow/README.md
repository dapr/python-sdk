# Example - Dapr Workflow Authoring

This document describes how to register a workflow and activities inside it and start running it.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

### Install requirements

You can install dapr SDK package using pip command:

<!-- STEP 
name: Install requirements
-->

```sh
pip3 install -r demo_workflow/requirements.txt

pip3 install dapr

dapr run --app-id orderapp --app-protocol grpc --dapr-grpc-port 4001 --components-path components --placement-host-address localhost:50005 -- python3 app.py
```

<!-- END_STEP -->