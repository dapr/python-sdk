# Example - Cryptography

This example demonstrates the [cryptography component] APIs in Dapr.
It demonstrates the following APIs:
- **encrypt**: Encrypt a string/file with keys from the local store
- **decrypt**: Decrypt a string/file with keys from the local store

It creates a client using `DaprClient`, uses a local store defined in
[`./components/crypto-localstorage.yaml`](./components/crypto-localstorage.yaml) and invokes cryptography API methods available as example.

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.10+](https://www.python.org/downloads/)

> In order to run this sample, make sure that OpenSSL is available on your system.

### Run the example

1. This sample requires a private RSA key and a 256-bit symmetric (AES) key. We will generate them using OpenSSL:

<!-- STEP
name: Generate crypto
timeout_seconds: 20
-->

```bash
mkdir -p keys
# Generate a private RSA key, 4096-bit keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out keys/rsa-private-key.pem
# Generate a 256-bit key for AES
openssl rand -out keys/symmetric-key-256 32
```

<!-- END_STEP -->

2. Run the Python service app with Dapr - crypto:

<!-- STEP
name: Run crypto example
expected_stdout_lines:
  - 'Running gRPC client synchronous API'
  - 'Running encrypt/decrypt operation on string'
  - 'Encrypted the message, got 856 bytes'
  - 'Decrypted the message, got 24 bytes'
  - 'The secret is "passw0rd"'
  - 'Running encrypt/decrypt operation on file'
  - 'Wrote encrypted data to encrypted.out'
  - 'Wrote decrypted data to decrypted.out.jpg'
  - "Exited App successfully"
output_match_mode: substring
timeout_seconds: 10
-->

```bash
dapr run --app-id crypto --resources-path ./components/ -- python3 crypto.py
```

<!-- END_STEP -->

3. Run the Python service app with Dapr - async crypto:

<!-- STEP
name: Run async crypto example
expected_stdout_lines:
  - 'Running gRPC client asynchronous API'
  - 'Running encrypt/decrypt operation on string'
  - 'Encrypted the message, got 856 bytes'
  - 'Decrypted the message, got 24 bytes'
  - 'The secret is "passw0rd"'
  - 'Running encrypt/decrypt operation on file'
  - 'Wrote encrypted data to encrypted.out'
  - 'Wrote decrypted data to decrypted.out.jpg'
  - "Exited App successfully"
output_match_mode: substring
timeout_seconds: 10
-->

```bash
dapr run --app-id crypto-async --resources-path ./components/ -- python3 crypto-async.py
```

<!-- END_STEP -->

### Cleanup

<!-- STEP
name: Clean up generated resources
timeout_seconds: 5
-->

```bash
rm -r keys
rm encrypted.out
rm decrypted.out.jpg
```

<!-- END_STEP -->

## Result

The output should be as follows:

```shell
Running gRPC client synchronous API
Running encrypt/decrypt operation on string
Encrypted the message, got 856 bytes
Decrypted the message, got 24 bytes
b'The secret is "passw0rd"'
Running encrypt/decrypt operation on file
Wrote encrypted data to encrypted.out
Wrote decrypted data to decrypted.out.jpg
Running gRPC client asynchronous API
Running encrypt/decrypt operation on string
Encrypted the message, got 856 bytes
Decrypted the message, got 24 bytes
b'The secret is "passw0rd"'
Running encrypt/decrypt operation on file
Wrote encrypted data to encrypted.out
Wrote decrypted data to decrypted.out.jpg
```
