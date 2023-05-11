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
```

<!-- END_STEP -->

## Run in self-hosted mode

<!-- STEP
name: Workflow Service
background: true
sleep: 5
timeout_seconds: 60
-->

1. Run Demo Workflow service in new terminal window


   ```bash
   cd demo_workflow
   dapr run --app-id demo-workflow --app-port 3000 -- uvicorn --port 3000 demo_workflow_service:app
   ```

2. Run Demo client in new terminal window


   ```bash
   # Run workflow client
   cd demo_workflow
   dapr run --app-id demo-workflow python3 demo_workflow_client.py
   ```

## Run DemoWorkflow on Kubernetes

1. Build and push docker image

   ```
   $ cd examples/demo_workflow/demo_workflow
   $ docker build -t [docker registry]/demo_workflow:latest .
   $ docker push [docker registry]/demo_workflow:latest
   $ cd ..
   ```

> For example, [docker registry] is docker hub account.

2. Follow [these steps](https://docs.dapr.io/getting-started/tutorials/configure-state-pubsub/#step-1-create-a-redis-store) to create a Redis store.

3. Once your store is created,  confirm validate `redis.yml` file in the `deploy` directory. 
    > **Note:** the `redis.yml` uses the secret created by `bitmany/redis` Helm chat to securely inject the password.

4. Apply the `redis.yml` file: `kubectl apply -f ./deploy/redis.yml` and observe that your state store was successfully configured!

   ```bash
   component.dapr.io/statestore configured
   ```
<TBD> Complete the steps @DeepanshuA
