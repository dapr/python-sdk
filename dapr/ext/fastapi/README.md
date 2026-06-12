# dapr.ext.fastapi

FastAPI integration for the Dapr Python SDK. Provides `DaprApp` for pub/sub
subscriptions and `DaprActor` for actor hosting.

```sh
pip install "dapr[fastapi]"
```

```python
from dapr.ext.fastapi import DaprApp, DaprActor
```

See the root [README](../../../README.md) for migration steps from the legacy
`dapr-ext-fastapi` distribution.