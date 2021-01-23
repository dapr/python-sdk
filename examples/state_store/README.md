# Example - Save and get state

This example demonstrates the Statestore APIs in Dapr.
It demonstrates the following APIs:
- **save state**: Save single or mutiple states to statestore
- **get state**: Get a single state from statestore
- **bulk get**: Get multiple states(Bulk get) from statestore
- **transaction**: Execute a transaction on supported statestores
- **delete state**: Delete specified key from statestore
- **etags**: Use of etag and error handling for etag mismatches

It creates a client using `DaprClient` and calls all the state API methods available as example.
It uses the default configuration from Dapr init in [self-hosted mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted). 

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr python-SDK

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

To run this example, the following code can be utilized:

```bash
cd examples/state_store
dapr run -- python3 state_store.py
```

The output should be as follows:

```
== APP == State store has successfully saved value_1 with key_1 as key

== APP == Cannot save due to bad etag. ErrorCode=StatusCode.ABORTED Details=failed saving state in state store statestore: possible etag mismatch. error from state store: ERR Error running script (call to f_83e03ec05d6a3b6fb48483accf5e594597b6058f): @user_script:1: user_script:1: failed to set key Warlockspring-Wolverine||key_1

== APP == State store has successfully saved value_2 with key_2 as key

== APP == State store has successfully saved value_3 with key_3 as key

== APP == Cannot save bulk due to bad etags. ErrorCode=StatusCode.ABORTED Details=failed saving state in state store statestore: possible etag mismatch. error from state store: ERR Error running script (call to f_83e03ec05d6a3b6fb48483accf5e594597b6058f): @user_script:1: user_script:1: failed to set key Warlockspring-Wolverine||key_2

== APP == Got value=b'value_1' eTag=1

== APP == Got items with etags: [(b'value_1_updated', '2'), (b'value_2', '2')]

== APP == Got value after delete: b''
```