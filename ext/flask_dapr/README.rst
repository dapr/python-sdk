Dapr flask extension
====================

|pypi|

.. |pypi| image:: https://badge.fury.io/py/flask-dapr.svg
   :target: https://pypi.org/project/flask-dapr/

This flask extension is used to:
- run the actor service
- subscribe to PubSub events

Installation
------------

::

    pip install flask-dapr

PubSub Events
-------------

```python
from flask import Flask, request
from flask_dapr import DaprApp

app = Flask('myapp')
dapr_app = DaprApp(app)
@dapr_app.subscribe(pubsub='pubsub', topic='some_topic', route='/some_endpoint')
def my_event_handler():
  # request.data contains pubsub event
  pass
```

References
----------

* `Dapr <https://github.com/dapr/dapr>`_
* `Dapr Python-SDK <https://github.com/dapr/python-sdk>`_
