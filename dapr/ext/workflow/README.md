# dapr.ext.workflow

Durable workflow orchestration for the Dapr Python SDK, built on a vendored
durabletask engine. Provides `WorkflowRuntime` and `DaprWorkflowClient`.

```sh
pip install "dapr[workflow]"
```

```python
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
```

See the root [README](../../../README.md) for migration steps from the legacy
`dapr-ext-workflow` distribution.