# Example - Statestore

This example demonstrates the Statestore APIs in Dapr.
It demonstrates the following APIs:
* save state: Save single or mutiple states to statestore
* get state: Get a single state from statestore
* bulk get: Get multiple states(Bulk get) from statestore
* transaction: Execute a transaction on supported statestores
* delete state: Delete specified key from statestore


It creates a client using `DaprClient` and calls all the state API methods available as example.
It uses the default configuration from Dapr init in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted). 

> **Note:** Make sure to use the latest proto bindings

## Running

To run this example, the following code can be utilized:

```bash
cd examples/state_store
dapr run --app-id stateapp --app-protocol grpc python3 state_store.py
```

The output should be as follows:

```
== APP == State store has successfully saved value_1 with key_1 as key

== APP == State store has successfully saved value_2 with key_2 as key

== APP == State store has successfully saved value_3 with key_3 as key

== APP == Got value: b'value_1'

== APP == Got items: [b'value_1_updated', b'value_2']

== APP == Got value after delete: b''
```