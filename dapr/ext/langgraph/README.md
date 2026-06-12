# dapr.ext.langgraph

LangGraph checkpoint persistence backed by any Dapr state store. Provides
`DaprCheckpointer`, which extends LangGraph's `BaseCheckpointSaver`.

```sh
pip install "dapr[langgraph]"
```

```python
from dapr.ext.langgraph import DaprCheckpointer
```

See the root [README](../../../README.md) for migration steps from the legacy
`dapr-ext-langgraph` distribution.