# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

import unittest

from datetime import timedelta
from dapr.actor.runtime.config import ActorRuntimeConfig, ActorReentrancyConfig


class ActorRuntimeConfigTests(unittest.TestCase):
    def test_default_config(self):
        config = ActorRuntimeConfig()

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._reentrancy, None)
        self.assertEqual(config._entities, [])
        self.assertNotIn('reentrancy', config.as_dict().keys())
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_default_config_with_reentrancy(self):
        reentrancyConfig = ActorReentrancyConfig(enabled=True)
        config = ActorRuntimeConfig(reentrancy=reentrancyConfig)

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._reentrancy, reentrancyConfig)
        self.assertEqual(config._entities, [])
        self.assertEqual(config.as_dict()['reentrancy'], reentrancyConfig.as_dict())
        self.assertEqual(config.as_dict()['reentrancy']['enabled'], True)
        self.assertEqual(config.as_dict()['reentrancy']['maxStackDepth'], 32)
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_update_entities(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1'])

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, ['actortype1'])
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_update_entities_two_types(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1', 'actortype1'])
        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, ['actortype1', 'actortype1'])
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_set_reminders_storage_partitions(self):
        config = ActorRuntimeConfig(reminders_storage_partitions=12)
        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertNotIn('reentrancy', config.as_dict().keys())
        self.assertEqual(config._reminders_storage_partitions, 12)
        self.assertEqual(config.as_dict()['remindersStoragePartitions'], 12)


if __name__ == '__main__':
    unittest.main()
