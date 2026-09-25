# dapr.ext.strands

Strands Agents session management backed by any Dapr state store. Provides
`DaprSessionManager` for distributed session, agent, and message persistence.

```sh
pip install "dapr[strands]"
```

```python
from dapr.ext.strands import DaprSessionManager
```

See the root [README](../../../README.md) for migration steps from the legacy
`dapr-ext-strands` distribution.