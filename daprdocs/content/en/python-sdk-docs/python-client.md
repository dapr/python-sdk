---
type: docs
title: "Getting started with the Dapr client Python SDK"
linkTitle: "Client"
weight: 10000
description: How to get up and running with the Dapr Python SDK
---

The Dapr client package allows you to interact with other Dapr applications from a Python application.

{{% alert title="Note" color="primary" %}}
 If you haven't already, [try out one of the quickstarts]({{< ref quickstarts >}}) for a quick walk-through on how to use the Dapr Python SDK with an API building block.

{{% /alert %}}

## Prerequisites

[Install the Dapr Python package]({{< ref "python#installation" >}}) before getting started.

## Import the client package

The `dapr` package contains the `DaprClient`, which is used to create and use a client.

```python
from dapr.clients import DaprClient
```

## Initialising the client
You can initialise a Dapr client in multiple ways:

#### Default values:
When you initialise the client without any parameters it will use the default values for a Dapr 
sidecar instance (`127.0.0.1:50001`).
```python
from dapr.clients import DaprClient

with DaprClient() as d:
    # use the client
```

#### Specifying an endpoint on initialisation:  
When passed as an argument in the constructor, the gRPC endpoint takes precedence over any 
configuration or environment variable.

```python
from dapr.clients import DaprClient

with DaprClient("mydomain:50051?tls=true") as d:
    # use the client
```  

#### Environment variables:  

##### Dapr Sidecar Endpoints
You can use the standardised `DAPR_GRPC_ENDPOINT` environment variable to
specify the gRPC endpoint. When this variable is set, the client can be initialised 
without any arguments:

```bash
export DAPR_GRPC_ENDPOINT="mydomain:50051?tls=true"
```
```python
from dapr.clients import DaprClient

with DaprClient() as d:
    # the client will use the endpoint specified in the environment variables
```  

The legacy environment variables `DAPR_RUNTIME_HOST`, `DAPR_HTTP_PORT` and `DAPR_GRPC_PORT` are 
also supported, but `DAPR_GRPC_ENDPOINT` takes precedence.

##### Dapr API Token
If your Dapr instance is configured to require the `DAPR_API_TOKEN` environment variable, you can
set it in the environment and the client will use it automatically.  
You can read more about Dapr API token authentication [here](https://docs.dapr.io/operations/security/api-token/).

##### Health timeout
On client initialisation, a health check is performed against the Dapr sidecar (`/healthz/outboud`).
The client will wait for the sidecar to be up and running before proceeding.  

The default timeout is 60 seconds, but it can be overridden by setting the `DAPR_HEALTH_TIMEOUT`
environment variable.


## Error handling
Initially, errors in Dapr followed the [Standard gRPC error model](https://grpc.io/docs/guides/error/#standard-error-model). However, to provide more detailed and informative error messages, in version 1.13 an enhanced error model has been introduced which aligns with the gRPC [Richer error model](https://grpc.io/docs/guides/error/#richer-error-model). In response, the Python SDK implemented `DaprGrpcError`, a custom exception class designed to improve the developer experience.  
It's important to note that the transition to using `DaprGrpcError` for all gRPC status exceptions is a work in progress. As of now, not every API call in the SDK has been updated to leverage this custom exception. We are actively working on this enhancement and welcome contributions from the community.

Example of handling `DaprGrpcError` exceptions when using the Dapr python-SDK:

```python
try:
    d.save_state(store_name=storeName, key=key, value=value)
except DaprGrpcError as err:
    print(f'Status code: {err.code()}')
    print(f"Message: {err.message()}")
    print(f"Error code: {err.error_code()}")
    print(f"Error info(reason): {err.error_info.reason}")
    print(f"Resource info (resource type): {err.resource_info.resource_type}")
    print(f"Resource info (resource name): {err.resource_info.resource_name}")
    print(f"Bad request (field): {err.bad_request.field_violations[0].field}")
    print(f"Bad request (description): {err.bad_request.field_violations[0].description}")
```


## Building blocks

The Python SDK allows you to interface with all of the [Dapr building blocks]({{< ref building-blocks >}}).

### Invoke a service

The Dapr Python SDK provides a simple API for invoking services via either HTTP or gRPC (deprecated). The protocol can be selected by setting the `DAPR_API_METHOD_INVOCATION_PROTOCOL` environment variable, defaulting to HTTP when unset. GRPC service invocation in Dapr is deprecated and GRPC proxying is recommended as an alternative.

```python 
from dapr.clients import DaprClient

with DaprClient() as d:
    # invoke a method (gRPC or HTTP GET)    
    resp = d.invoke_method('service-to-invoke', 'method-to-invoke', data='{"message":"Hello World"}')

    # for other HTTP verbs the verb must be specified
    # invoke a 'POST' method (HTTP only)    
    resp = d.invoke_method('service-to-invoke', 'method-to-invoke', data='{"id":"100", "FirstName":"Value", "LastName":"Value"}', http_verb='post')
```

The base endpoint for HTTP api calls is specified in the `DAPR_HTTP_ENDPOINT` environment variable.
If this variable is not set, the endpoint value is derived from the `DAPR_RUNTIME_HOST` and `DAPR_HTTP_PORT` variables, whose default values are `127.0.0.1` and `3500` accordingly.

The base endpoint for gRPC calls is the one used for the client initialisation ([explained above](#initialising-the-client)).


- For a full guide on service invocation visit [How-To: Invoke a service]({{< ref howto-invoke-discover-services.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/invoke-simple) for code samples and instructions to try out service invocation.

### Save & get application state

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    # Save state
    d.save_state(store_name="statestore", key="key1", value="value1")

    # Get state
    data = d.get_state(store_name="statestore", key="key1").data

    # Delete state
    d.delete_state(store_name="statestore", key="key1")
```

- For a full list of state operations visit [How-To: Get & save state]({{< ref howto-get-save-state.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/state_store) for code samples and instructions to try out state management.

### Query application state (Alpha)

```python
    from dapr import DaprClient

    query = '''
    {
        "filter": {
            "EQ": { "state": "CA" }
        },
        "sort": [
            {
                "key": "person.id",
                "order": "DESC"
            }
        ]
    }
    '''

    with DaprClient() as d:
        resp = d.query_state(
            store_name='state_store',
            query=query,
            states_metadata={"metakey": "metavalue"},  # optional
        )
```

- For a full list of state store query options visit [How-To: Query state]({{< ref howto-state-query-api.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/state_store_query) for code samples and instructions to try out state store querying.

### Publish & subscribe to messages

#### Publish messages

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.publish_event(pubsub_name='pubsub', topic_name='TOPIC_A', data='{"message":"Hello World"}')
```

#### Subscribe to messages

```python
from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
import json

app = App()

# Default subscription for a topic
@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
def mytopic(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Received: id={data["id"]}, message="{data ["message"]}"' 
          ' content_type="{event.content_type}"',flush=True)

# Specific handler using Pub/Sub routing
@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A',
               rule=Rule("event.type == \"important\"", 1))
def mytopic_important(event: v1.Event) -> None:
    data = json.loads(event.Data())
    print(f'Received: id={data["id"]}, message="{data ["message"]}"' 
          ' content_type="{event.content_type}"',flush=True)
```

- For more information about pub/sub, visit [How-To: Publish & subscribe]({{< ref howto-publish-subscribe.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/pubsub-simple) for code samples and instructions to try out pub/sub.


### Interact with output bindings

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.invoke_binding(binding_name='kafkaBinding', operation='create', data='{"message":"Hello World"}')
```

- For a full guide on output bindings visit [How-To: Use bindings]({{< ref howto-bindings.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/invoke-binding) for code samples and instructions to try out output bindings.

### Retrieve secrets

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    resp = d.get_secret(store_name='localsecretstore', key='secretKey')
```

- For a full guide on secrets visit [How-To: Retrieve secrets]({{< ref howto-secrets.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/secret_store) for code samples and instructions to try out retrieving secrets

### Configuration

#### Get configuration

```python
from dapr.clients import DaprClient

with DaprClient() as d:
    # Get Configuration
    configuration = d.get_configuration(store_name='configurationstore', keys=['orderId'], config_metadata={})
```

#### Subscribe to configuration

```python
import asyncio
from time import sleep
from dapr.clients import DaprClient

async def executeConfiguration():
    with DaprClient() as d:
        storeName = 'configurationstore'

        key = 'orderId'

        # Wait for sidecar to be up within 20 seconds.
        d.wait(20)

        # Subscribe to configuration by key.
        configuration = await d.subscribe_configuration(store_name=storeName, keys=[key], config_metadata={})
        while True:
            if configuration != None:
                items = configuration.get_items()
                for key, item in items:
                    print(f"Subscribe key={key} value={item.value} version={item.version}", flush=True)
            else:
                print("Nothing yet")
        sleep(5)

asyncio.run(executeConfiguration())
```

- Learn more about managing configurations via the [How-To: Manage configuration]({{< ref howto-manage-configuration.md >}}) guide.
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples/configuration) for code samples and instructions to try out configuration.

### Distributed Lock

```python
from dapr.clients import DaprClient

def main():
    # Lock parameters
    store_name = 'lockstore'  # as defined in components/lockstore.yaml
    resource_id = 'example-lock-resource'
    client_id = 'example-client-id'
    expiry_in_seconds = 60

    with DaprClient() as dapr:
        print('Will try to acquire a lock from lock store named [%s]' % store_name)
        print('The lock is for a resource named [%s]' % resource_id)
        print('The client identifier is [%s]' % client_id)
        print('The lock will will expire in %s seconds.' % expiry_in_seconds)

        with dapr.try_lock(store_name, resource_id, client_id, expiry_in_seconds) as lock_result:
            assert lock_result.success, 'Failed to acquire the lock. Aborting.'
            print('Lock acquired successfully!!!')

        # At this point the lock was released - by magic of the `with` clause ;)
        unlock_result = dapr.unlock(store_name, resource_id, client_id)
        print('We already released the lock so unlocking will not work.')
        print('We tried to unlock it anyway and got back [%s]' % unlock_result.status)
```

- Learn more about using a distributed lock: [How-To: Use a lock]({{< ref howto-use-distributed-lock.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/blob/master/examples/distributed_lock) for code samples and instructions to try out distributed lock.

### Workflow

```python
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowContext, WorkflowActivityContext
from dapr.clients import DaprClient

instanceId = "exampleInstanceID"
workflowComponent = "dapr"
workflowName = "hello_world_wf"
eventName = "event1"
eventData = "eventData"

def main():
    with DaprClient() as d:
        host = settings.DAPR_RUNTIME_HOST
        port = settings.DAPR_GRPC_PORT
        workflowRuntime = WorkflowRuntime(host, port)
        workflowRuntime = WorkflowRuntime()
        workflowRuntime.register_workflow(hello_world_wf)
        workflowRuntime.register_activity(hello_act)
        workflowRuntime.start()

        # Start the workflow
        start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                        workflow_name=workflowName, input=inputData, workflow_options=workflowOptions)
        print(f"start_resp {start_resp.instance_id}")

        # ...

        # Pause Test
        d.pause_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after pause call: {getResponse.runtime_status}")

        # Resume Test
        d.resume_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after resume call: {getResponse.runtime_status}")
        
        sleep(1)
        # Raise event
        d.raise_workflow_event(instance_id=instanceId, workflow_component=workflowComponent,
                    event_name=eventName, event_data=eventData)

        sleep(5)
        # Purge Test
        d.purge_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        try:
            getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        except DaprInternalError as err:
            if nonExistentIDError in err._message:
                print("Instance Successfully Purged")

        
        # Kick off another workflow for termination purposes 
        # This will also test using the same instance ID on a new workflow after
        # the old instance was purged
        start_resp = d.start_workflow(instance_id=instanceId, workflow_component=workflowComponent,
                        workflow_name=workflowName, input=inputData, workflow_options=workflowOptions)
        print(f"start_resp {start_resp.instance_id}")

        # Terminate Test
        d.terminate_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        sleep(1)
        getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        print(f"Get response from {workflowName} after terminate call: {getResponse.runtime_status}")

        # Purge Test
        d.purge_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        try:
            getResponse = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
        except DaprInternalError as err:
            if nonExistentIDError in err._message:
                print("Instance Successfully Purged")

        workflowRuntime.shutdown()
```

- Learn more about authoring and managing workflows: 
  - [How-To: Author a workflow]({{< ref howto-author-workflow.md >}}).
  - [How-To: Manage a workflow]({{< ref howto-manage-workflow.md >}}).
- Visit [Python SDK examples](https://github.com/dapr/python-sdk/blob/master/examples/demo_workflow/app.py) for code samples and instructions to try out Dapr Workflow.


## Related links
[Python SDK examples](https://github.com/dapr/python-sdk/tree/master/examples)
