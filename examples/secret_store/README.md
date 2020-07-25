# Example - Secret Store

This example utilizes a local secret store to show how to retrieve secrets using dapr
It creates a dapr client and calls the `get_secret` method in the `DaprClient`.

> **Note:** Make sure to use the latest proto bindings

## Running

To run this example, use the following command:

```bash
dapr run --app-id=secretsapp --protocol grpc --components-path components/ python example.py
```

You should be able to see the following output:

```bash

== APP == Got!

== APP == {'secretKey': 'secretValue'}
```

## Clean Up

Run the following command in a new terminal to stop the app
```bash
dapr stop --app-id=secretsapp
```


You can replace local secret store with any other secret stores that dapr supports like Kubernetes, Hashicorp Vault, Azure KeyVault etc.

