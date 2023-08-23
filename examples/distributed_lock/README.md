# Example - Acquire and release distributed locks

This example demonstrates the [Distributed Lock component] APIs in Dapr.
It demonstrates the following APIs:
- **try_lock**: Attempts to acquire a distributed lock from the lock store.
- **unlock**: Attempts to release (a previously acquired) distributed lock

It creates a client using `DaprClient`, uses a local lock store defined in
[`./components/lockstore.yaml`](./components/lockstore.yaml) and invokes
all the distributed lock API methods available as example.

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
name: Run state store example
expected_stdout_lines:
  - "== APP == Will try to acquire a lock from lock store named [lockstore]"
  - "== APP == The lock is for a resource named [example-lock-resource]"
  - "== APP == The client identifier is [example-client-id]"
  - "== APP == The lock will will expire in 60 seconds."
  - "== APP == Lock acquired successfully!!!"
  - "== APP == We already released the lock so unlocking will not work."
  - "== APP == We tried to unlock it anyway and got back [UnlockResponseStatus.lock_does_not_exist]"
timeout_seconds: 5
-->

```bash
dapr run --app-id=locksapp --app-protocol grpc --resources-path components/ python3 lock.py
```
<!-- END_STEP -->

The output should be as follows:

```
== APP == Will try to acquire a lock from lock store named [lockstore]
== APP == The lock is for a resource named [example-lock-resource]
== APP == The client identifier is [example-client-id]
== APP == The lock will will expire in 60 seconds.
== APP == Lock acquired successfully!!!
== APP == We already released the lock so unlocking will not work.
== APP == We tried to unlock it anyway and got back [UnlockResponseStatus.lock_does_not_exist]
```

## Error Handling

The Dapr python-sdk will pass through errors that it receives from the Dapr runtime.

[Distributed Lock component]: https://docs.dapr.io/developing-applications/building-blocks/distributed-lock/