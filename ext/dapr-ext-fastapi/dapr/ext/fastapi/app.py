# -*- coding: utf-8 -*-
"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from typing import Dict, List, Optional
from fastapi import FastAPI  # type: ignore


class DaprApp:
    """
    Wraps a regular FastAPI app instance to enhance it with Dapr specific functionality.

    Args:
        app_instance: The FastAPI instance to wrap.
    """

    def __init__(self, app_instance: FastAPI, router_tags: Optional[List[str]] = ['PubSub']):
        # The router_tags should be added to all magic Dapr App PubSub methods implemented here
        self._router_tags = router_tags
        self._app = app_instance
        self._subscriptions: List[Dict[str, object]] = []

        self._app.add_api_route(
            '/dapr/subscribe', self._get_subscriptions, methods=['GET'], tags=self._router_tags
        )

    def subscribe(
        self,
        pubsub: str,
        topic: str,
        metadata: Optional[Dict[str, str]] = {},
        route: Optional[str] = None,
        dead_letter_topic: Optional[str] = None,
    ):
        """
        Subscribes to a topic on a pub/sub component.

        Subscriptions made through this method will show up when you GET /dapr/subscribe.

        Example:
            The following sample demonstrates how to use the subscribe method to register an
            event handler for the application on a pub/sub component named `pubsub`.

            >> from fastapi import Body, FastAPI
            >> from dapr.ext.fastapi import DaprApp

            >> app = FastAPI()
            >> dapr_app = DaprApp(app)
            >> @dapr_app.subscribe(pubsub='pubsub', topic='some_topic', route='/some_endpoint')
            >> def my_event_handler(event_data = Body()):
            >>    print(event_data)

        Args:
            pubsub: The name of the pub/sub component.
            topic: The name of the topic.
            metadata: The metadata for the subscription.
            route:
                The HTTP route to register for the event subscription. By default we'll
                generate one that matches the pattern /events/{pubsub}/{topic}. You can
                override this with your own route.
            dead_letter_topic: The name of the dead letter topic to use for the subscription.

        Returns:
            The decorator for the function.
        """

        def decorator(func):
            event_handler_route = f'/events/{pubsub}/{topic}' if route is None else route

            self._app.add_api_route(
                event_handler_route, func, methods=['POST'], tags=self._router_tags
            )

            self._subscriptions.append(
                {
                    'pubsubname': pubsub,
                    'topic': topic,
                    'route': event_handler_route,
                    'metadata': metadata,
                    **(
                        {'deadLetterTopic': dead_letter_topic}
                        if dead_letter_topic is not None
                        else {}
                    ),
                }
            )

        return decorator

    def _get_subscriptions(self):
        return self._subscriptions
