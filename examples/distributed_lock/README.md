# Example - Acquire and release distributed locks

This example demonstrates the [Distributed Locks component] APIs in Dapr.
It demonstrates the following APIs:
- **try lock**: Attempts to acquire a distributed lock from the lock store.
- **unlock**: Attempts to release (a previously acquired) distributed lock

It creates a client using `DaprClient`, uses a local lock store defined in
[`./components/lockstore.yaml`](./components/lockstore.yaml) and invokes
all the distributed lock API methods available as example.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.7+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

Change directory to this folder:
```bash
cd examples/distributed_lock
```

To run this example, the following code can be utilized:

<!-- STEP
name: Run state store example
expected_stdout_lines:
  - "== APP == INFO:root:Will attempt to acquire a lock for resource=python-sdk-example-lock-resource"
  - "== APP == INFO:root:This client identifier is client-271c0755-c603-4cea-aa17-88c6292c1d0d"
  - "== APP == INFO:root:This lock will will expire in 60 seconds."
  - "== APP == example.py:31: UserWarning: The Distributed Lock API is an Alpha version and is subject to change."
  - "== APP ==   with dapr.try_lock(store_name, resource_id, client_id, expiry_in_seconds) as lock_result:"
  - "== APP == INFO:root:Lock acquired successfully lock_result=TryLockResponse(success=True, client=<dapr.clients.DaprClient object at   - " 0x7f18ccd91a00>, store_name='lockstore', resource_id='python-sdk-example-lock-resource',   - " lock_owner='client-271c0755-c603-4cea-aa17-88c6292c1d0d')"
  - "== APP == /home/tmacam/projects/dapr-python-sdk/dapr/clients/grpc/_response.py:790: UserWarning: The Distributed Lock API is an   - " Alpha version and is subject to change."
  - "== APP ==   self.client.unlock(self.store_name, self.resource_id, self.lock_owner)"
  - "== APP == example.py:36: UserWarning: The Distributed Lock API is an Alpha version and is subject to change."
  - "== APP ==   unlock_result = dapr.unlock(store_name, resource_id, client_id)"
  - "== APP == INFO:root:We already released the lock so unlocking will not work - unlock_result=UnlockResponseStatus.lock_does_not_exist"
timeout_seconds: 5
-->

```bash
dapr run --app-id=locksapp --app-protocol grpc --components-path components/ python3 example.py
```
<!-- END_STEP -->

The output should be as follows:

```
== APP == INFO:root:Will attempt to acquire a lock for resource=python-sdk-example-lock-resource
== APP == INFO:root:This client identifier is client-271c0755-c603-4cea-aa17-88c6292c1d0d
== APP == INFO:root:This lock will will expire in 60 seconds.
== APP == example.py:31: UserWarning: The Distributed Lock API is an Alpha version and is subject to change.
== APP ==   with dapr.try_lock(store_name, resource_id, client_id, expiry_in_seconds) as lock_result:
== APP == INFO:root:Lock acquired successfully lock_result=TryLockResponse(success=True, client=<dapr.clients.DaprClient object at 0x7f18ccd91a00>, store_name='lockstore', resource_id='python-sdk-example-lock-resource', lock_owner='client-271c0755-c603-4cea-aa17-88c6292c1d0d')
== APP == /home/tmacam/projects/dapr-python-sdk/dapr/clients/grpc/_response.py:790: UserWarning: The Distributed Lock API is an Alpha version and is subject to change.
== APP ==   self.client.unlock(self.store_name, self.resource_id, self.lock_owner)
== APP == example.py:36: UserWarning: The Distributed Lock API is an Alpha version and is subject to change.
== APP ==   unlock_result = dapr.unlock(store_name, resource_id, client_id)
== APP == INFO:root:We already released the lock so unlocking will not work - unlock_result=UnlockResponseStatus.lock_does_not_exist
```

## Error Handling

The Dapr python-sdk will pass through errors that it receives from the Dapr runtime.

TODO(tmacam): Should I describe error-handling for both `try_lock` and `unlock`

[Distributed Locks component]: https://docs.dapr.io/developing-applications/building-blocks/distributed-lock/