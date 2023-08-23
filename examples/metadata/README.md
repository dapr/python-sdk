# Example - Inspect Dapr runtime metadata

This example demonstrates the usage of Dapr [Metadata API] and of the two
two methods in that API:
1. **get_metadata**: Gets the Dapr sidecar information provided by the Metadata
   Endpoint.
2. **set_metadata**: Adds a custom label to the Dapr sidecar information stored
   by the Metadata endpoint.

It creates a client using `DaprClient`, uses a set of components defined in the 
[`./components/`](./components/) folder and invokes the two APIs from
[Metadata API].


## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

To run this example, the following code can be utilized:

<!-- STEP
name: Run metadata example
output_match_mode: substring
expected_stdout_lines:
  - "== APP == First, we will assign a new custom label to Dapr sidecar"
  - "== APP == Now, we will fetch the sidecar's metadata"
  - "== APP == And this is what we got:"
  - "== APP ==   application_id: my-metadata-app"
  - "== APP ==   active_actors_count: {}"
  - "== APP ==   registered_components:"
  - "== APP ==     name=lockstore type=lock.redis version= capabilities=[]"
  - "== APP ==     name=pubsub type=pubsub.redis version=v1 capabilities=[]"
  - "== APP ==     name=statestore type=state.redis version=v1 capabilities=['ACTOR', 'ETAG', 'TRANSACTIONAL'"
  - "== APP == We will update our custom label value and check it was persisted"
  - "== APP == We added a custom label named [is-this-our-metadata-example]"
  - "== APP == Its old value was [yes] but now it is [You bet it is!]"
timeout_seconds: 10
-->

```bash
dapr run --app-id=my-metadata-app --app-protocol grpc --resources-path components/ python3 app.py
```
<!-- END_STEP -->

The output should be as follows:

```
== APP == First, we will assign a new custom label to Dapr sidecar
== APP == Now, we will fetch the sidecar's metadata
== APP == And this is what we got:
== APP ==   application_id: my-metadata-app
== APP ==   active_actors_count: {}
== APP ==   registered_components:
== APP ==     name=lockstore type=lock.redis version= capabilities=[]
== APP ==     name=pubsub type=pubsub.redis version=v1 capabilities=[]
== APP ==     name=statestore type=state.redis version=v1 capabilities=['ACTOR', 'ETAG', 'TRANSACTIONAL', 'TTL']
== APP == We will update our custom label value and check it was persisted
== APP == We added a custom label named [is-this-our-metadata-example]
== APP == Its old value was [yes] but now it is [You bet it is!]
```

## Error Handling

The Dapr python-sdk will pass through errors that it receives from the Dapr runtime.

[Metadata API]: https://docs.dapr.io/reference/api/metadata_api/
