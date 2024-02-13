import json
import unittest

from flask import Flask
from flask_dapr import DaprApp


class DaprAppTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask('test_app')
        self.app.testing = True
        self.dapr_app = DaprApp(self.app)
        self.client = self.app.test_client()

    def test_subscribe_subscription_registered(self):
        @self.dapr_app.subscribe(pubsub='pubsub', topic='test')
        def event_handler():
            return 'default route'

        self.assertEqual(len(self.dapr_app._subscriptions), 1)

        self.assertIn('/dapr/subscribe', [r.rule for r in self.app.url_map.iter_rules()])
        self.assertIn('/events/pubsub/test', [r.rule for r in self.app.url_map.iter_rules()])

        response = self.client.get('/dapr/subscribe')
        self.assertEqual(
            [
                {
                    'pubsubname': 'pubsub',
                    'topic': 'test',
                    'route': '/events/pubsub/test',
                    'metadata': {},
                }
            ],
            json.loads(response.data),
        )

        response = self.client.post('/events/pubsub/test', json={'body': 'new message'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), 'default route')

    def test_subscribe_with_route_subscription_registered_with_custom_route(self):
        @self.dapr_app.subscribe(pubsub='pubsub', topic='test', route='/do-something')
        def event_handler():
            return 'custom route'

        self.assertEqual(len(self.dapr_app._subscriptions), 1)

        self.assertIn('/dapr/subscribe', [r.rule for r in self.app.url_map.iter_rules()])
        self.assertIn('/do-something', [r.rule for r in self.app.url_map.iter_rules()])

        response = self.client.get('/dapr/subscribe')
        self.assertEqual(
            [{'pubsubname': 'pubsub', 'topic': 'test', 'route': '/do-something', 'metadata': {}}],
            json.loads(response.data),
        )

        response = self.client.post('/do-something', json={'body': 'new message'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), 'custom route')

    def test_subscribe_metadata(self):
        handler_metadata = {'rawPayload': 'true'}

        @self.dapr_app.subscribe(pubsub='pubsub', topic='test', metadata=handler_metadata)
        def event_handler():
            return 'custom metadata'

        self.assertEqual((self.dapr_app._subscriptions[0]['metadata']['rawPayload']), 'true')

        response = self.client.get('/dapr/subscribe')
        self.assertEqual(
            [
                {
                    'pubsubname': 'pubsub',
                    'topic': 'test',
                    'route': '/events/pubsub/test',
                    'metadata': {'rawPayload': 'true'},
                }
            ],
            json.loads(response.data),
        )

        response = self.client.post('/events/pubsub/test', json={'body': 'new message'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), 'custom metadata')

    def test_subscribe_dead_letter(self):
        dead_letter_topic = 'dead-test'

        @self.dapr_app.subscribe(pubsub='pubsub', topic='test', dead_letter_topic=dead_letter_topic)
        def event_handler():
            return 'dead letter test'

        self.assertEqual((self.dapr_app._subscriptions[0]['deadLetterTopic']), dead_letter_topic)

        response = self.client.get('/dapr/subscribe')
        self.assertEqual(
            [
                {
                    'pubsubname': 'pubsub',
                    'topic': 'test',
                    'route': '/events/pubsub/test',
                    'metadata': {},
                    'deadLetterTopic': dead_letter_topic,
                }
            ],
            json.loads(response.data),
        )

        response = self.client.post('/events/pubsub/test', json={'body': 'new message'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), 'dead letter test')


if __name__ == '__main__':
    unittest.main()
