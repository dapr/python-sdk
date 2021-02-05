# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

import unittest

from datetime import timedelta
from dapr.actor.runtime.config import ActorRuntimeConfig


class ActorRuntimeConfigTests(unittest.TestCase):
    def test_default_config(self):
        config = ActorRuntimeConfig()

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, [])

    def test_update_entities(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1'])

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, ['actortype1'])

    def test_update_entities_two_types(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1', 'actortype1'])
        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, ['actortype1', 'actortype1'])


if __name__ == '__main__':
    unittest.main()
