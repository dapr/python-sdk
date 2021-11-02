from fastapi import FastAPI
from dapr.ext.fastapi import DaprApp


def test_subscribe_subscription_registered():
    app = FastAPI()
    dapr_app = DaprApp(app)

    @dapr_app.subscribe(pubsub="pubsub", topic="test")
    def event_handler(event_data):
        pass

    assert len(dapr_app._subscriptions) == 1
    assert len(app.router.routes) == 2

    assert app.router.routes[0].path == "/dapr/subscribe"
    assert app.router.routes[1].route == "/events/pubsub/test"


def test_subscribe_with_route_subscription_registered_with_custom_route():
    app = FastAPI()
    dapr_app = DaprApp(app)

    @dapr_app.subscribe(pubsub="pubsub", topic="test", route="/do-something")
    def event_handler(event_data):
        pass

    assert len(dapr_app._subscriptions) == 1
    assert len(app.router.routes) == 2

    assert app.router.routes[0].path == "/dapr/subscribe"
    assert app.router.routes[1].route == "/do-something"


def test_subscribe_metadata():
    app = FastAPI()
    dapr_app = DaprApp(app)

    handler_metadata = {"rawPayload": "true"}

    @dapr_app.subscribe(pubsub="pubsub",
                        topic="test",
                        metadata=handler_metadata)
    def event_handler(event_data):
        pass

    assert (dapr_app._subscriptions[0]["metadata"]["rawPayload"]) == "true"
