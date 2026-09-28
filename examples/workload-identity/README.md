# Example - Workload identity federation

Authenticates the Dapr client with a short-lived token instead of a static `DAPR_API_TOKEN`,
without handing the workload any secret up front:

1. The workload's platform issues it an identity token, for example a Kubernetes projected
   service account token or a cloud provider's workload identity token.
2. The client exchanges that token at an RFC 8693 token exchange endpoint that trusts the
   platform's issuer.
3. The client sends the exchanged token to Dapr as `dapr-api-token`, and exchanges a new one
   ahead of its expiry.

The Dapr endpoint must use TLS, for example `DAPR_GRPC_ENDPOINT=dapr.example.com:443?tls=true`.

This is an API reference rather than a `dapr run` example, because a local `daprd` doesn't
validate exchanged tokens. `tests/credentials/integration/` runs the same code against local
TLS servers.

## Install

```bash
pip3 install "dapr[workload-identity]"
```

## Kubernetes projected service account token

Project a token whose audience is the token exchange endpoint, not the Kubernetes API server,
so it can't be replayed elsewhere:

```yaml
volumes:
  - name: dapr-identity
    projected:
      sources:
        - serviceAccountToken:
            path: token
            audience: https://sts.example.com
            expirationSeconds: 3600
```

Mount it at `/var/run/secrets/dapr.io/serviceaccount`, then:

```python
from dapr.clients import DaprClient
from dapr.credentials import CredentialManager, kubernetes_service_account_source
from dapr.credentials.oauth2 import RFC8693TokenExchangeProvider

provider = RFC8693TokenExchangeProvider(
    token_url='https://sts.example.com/token',
    attestation=kubernetes_service_account_source(),  # re-read on every exchange
    audience='dapr',
)
credential_manager = CredentialManager(provider)

with DaprClient(credential_manager=credential_manager) as client:
    print(client.get_metadata())
```

The kubelet rotates the projected token, and each exchange reads the current one.

## Other platforms

`CallableAttestationSource` fetches the subject token from anywhere, such as a cloud metadata
endpoint or a CI system's OIDC endpoint:

```python
from dapr.credentials import CallableAttestationSource

attestation = CallableAttestationSource(fetch_platform_token)
```

`FileAttestationSource(path)` reads any other token file.

The same providers work with the async client (`dapr.aio.clients.DaprClient`) through
`dapr.credentials.AsyncCredentialManager`, and with `dapr.clients.http.client.DaprHttpClient`.

## Configuration through environment variables

`DaprClient()` builds a credential manager from these settings when no `credential_manager` is
passed. They take precedence over `DAPR_API_TOKEN`, with a warning:

```bash
export DAPR_WORKLOAD_IDENTITY_TOKEN_URL=https://sts.example.com/token
export DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH=/var/run/secrets/dapr.io/serviceaccount/token
export DAPR_WORKLOAD_IDENTITY_AUDIENCE=dapr   # optional
export DAPR_WORKLOAD_IDENTITY_SCOPE=...       # optional
```
