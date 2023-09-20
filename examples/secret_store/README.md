# Example - Retrieve a secret from a secret store

This example utilizes a local secret store to show how to retrieve secrets using dapr
It creates a dapr client and calls the `get_secret` method in the `DaprClient`.
This example also illustrates the use of access control for secrets.

> **Note:** Make sure to use the latest proto bindings

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->
```bash
pip3 install dapr dapr-ext-grpc
```

## Run the example

Change directory to this folder:
```bash
cd examples/secret_store
```

To run this example, use the following command:

<!-- STEP
name: Run secret store example
expected_stdout_lines:
  - "== APP == Got!"
  - "== APP == {'secretKey': 'secretValue'}"
  - "== APP == Got!"
  - "== APP == [('random', {'random': 'randomValue'}), ('secretKey', {'secretKey': 'secretValue'})]"
  - "== APP == Got!"
  - "== APP == {'random': 'randomValue'}"
timeout_seconds: 2
-->

```bash
dapr run --app-id=secretsapp --app-protocol grpc --resources-path components/ python3 example.py
```

<!-- END_STEP -->

You should be able to see the following output:
```
== APP == Got!
== APP == {'secretKey': 'secretValue'}
== APP == Got!
== APP == [('random', {'random': 'randomValue'}), ('secretKey', {'secretKey': 'secretValue'})]
== APP == Got!
== APP == {'random': 'randomValue'}
```

In `config.yaml` you can see that the `localsecretstore` secret store has been defined with some restricted permissions.

```yaml
apiVersion: dapr.io/v1alpha1
kind: Configuration
metadata:
  name: daprConfig
spec:
  secrets:
    scopes:
        - storeName: "localsecretstore"
          defaultAccess: "deny"
          allowedSecrets: ["secretKey",]
```

The above configuration defines that the default access permission for the `localsecretstore` is `deny` and that only the 
key `secretKey` is allowed to be accessed from the store.

To see this run the same `example.py` app with the following command: 

<!-- STEP
name: Run secret store example with access config
expected_stdout_lines:
  - "== APP == Got!"
  - "== APP == {'secretKey': 'secretValue'}"
  - "== APP == Got!"
  - "== APP == [('secretKey', {'secretKey': 'secretValue'})]"
  - "== APP == Got expected error for accessing random key"
timeout_seconds: 2
-->

```bash
dapr run --app-id=secretsapp --app-protocol grpc --config config.yaml --resources-path components/ python3 example.py
```

<!-- END_STEP -->

The above command overrides the default configuration file with the `--config` flag.

The output should be as follows:
```
== APP == Got!
== APP == {'secretKey': 'secretValue'}
== APP == Got!
== APP == [('secretKey', {'secretKey': 'secretValue'})]
== APP == Got expected error for accessing random key
```

It can be seen that when it tried to get the random key again, it fails as by default the access is denied for any key 
unless defined in the `allowedSecrets` list.

## Cleanup

Either press CTRL + C to quit the app or run the following command in a new terminal to stop the app
```bash
dapr stop --app-id=secretsapp
```


You can replace local secret store with any other secret stores that dapr supports like Kubernetes, Hashicorp Vault, Azure KeyVault etc.

