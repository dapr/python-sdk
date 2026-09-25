# dapr.ext.flask

Flask integration for the Dapr Python SDK. Provides `DaprApp` for pub/sub
subscriptions and `DaprActor` for actor hosting.

```sh
pip install "dapr[flask]"
```

```python
from flask import Flask, request
from dapr.ext.flask import DaprApp

app = Flask('myapp')
dapr_app = DaprApp(app)

@dapr_app.subscribe(pubsub='pubsub', topic='some_topic', route='/some_endpoint')
def my_event_handler():
    # request.data contains the pubsub event
    pass
```

The legacy top-level `flask_dapr` import path is still available as a thin
shim that emits a `FutureWarning`. See the root [README](../../../README.md)
for migration steps from the legacy `flask-dapr` distribution.