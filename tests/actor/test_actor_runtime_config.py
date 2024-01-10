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
from dapr.actor.runtime.config import ActorRuntimeConfig, ActorReentrancyConfig, ActorTypeConfig


class ActorTypeConfigTests(unittest.TestCase):
    def test_default_config(self):
        config = ActorTypeConfig('testactor')
        self.assertEqual(config._actor_idle_timeout, None)
        self.assertEqual(config._actor_scan_interval, None)
        self.assertEqual(config._drain_ongoing_call_timeout, None)
        self.assertEqual(config._drain_rebalanced_actors, None)
        self.assertEqual(config._reentrancy, None)
        self.assertEqual(config.as_dict()['entities'], ['testactor'])
        keys = config.as_dict().keys()
        self.assertNotIn('reentrancy', keys)
        self.assertNotIn('remindersStoragePartitions', keys)
        self.assertNotIn('actorIdleTimeout', keys)
        self.assertNotIn('actorScanInterval', keys)
        self.assertNotIn('drainOngoingCallTimeout', keys)
        self.assertNotIn('drainRebalancedActors', keys)

    def test_complete_config(self):
        config = ActorTypeConfig(
            'testactor',
            actor_idle_timeout=timedelta(seconds=3600),
            actor_scan_interval=timedelta(seconds=30),
            drain_ongoing_call_timeout=timedelta(seconds=60),
            drain_rebalanced_actors=False,
            reentrancy=ActorReentrancyConfig(enabled=True),
            reminders_storage_partitions=10,
        )
        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, False)
        self.assertEqual(config._reentrancy._enabled, True)
        self.assertEqual(config._reentrancy._maxStackDepth, 32)
        d = config.as_dict()
        self.assertEqual(d['entities'], ['testactor'])
        self.assertEqual(d['reentrancy']['enabled'], True)
        self.assertEqual(d['reentrancy']['maxStackDepth'], 32)
        self.assertEqual(d['remindersStoragePartitions'], 10)
        self.assertEqual(d['actorIdleTimeout'], timedelta(seconds=3600))
        self.assertEqual(d['actorScanInterval'], timedelta(seconds=30))
        self.assertEqual(d['drainOngoingCallTimeout'], timedelta(seconds=60))
        self.assertEqual(d['drainRebalancedActors'], False)


class ActorRuntimeConfigTests(unittest.TestCase):
    def test_default_config(self):
        config = ActorRuntimeConfig()

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._reentrancy, None)
        self.assertEqual(config._entities, set())
        self.assertEqual(config._entitiesConfig, [])
        self.assertNotIn('reentrancy', config.as_dict().keys())
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())
        self.assertEqual(config.as_dict()['entitiesConfig'], [])

    def test_default_config_with_reentrancy(self):
        reentrancyConfig = ActorReentrancyConfig(enabled=True)
        config = ActorRuntimeConfig(reentrancy=reentrancyConfig)

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._reentrancy, reentrancyConfig)
        self.assertEqual(config._entities, set())
        self.assertEqual(config._entitiesConfig, [])
        self.assertEqual(config.as_dict()['reentrancy'], reentrancyConfig.as_dict())
        self.assertEqual(config.as_dict()['reentrancy']['enabled'], True)
        self.assertEqual(config.as_dict()['reentrancy']['maxStackDepth'], 32)
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_config_with_actor_type_config(self):
        typeConfig1 = ActorTypeConfig(
            'testactor1',
            actor_scan_interval=timedelta(seconds=10),
            reentrancy=ActorReentrancyConfig(enabled=True),
        )
        typeConfig2 = ActorTypeConfig(
            'testactor2',
            drain_ongoing_call_timeout=timedelta(seconds=60),
            reminders_storage_partitions=10,
        )
        config = ActorRuntimeConfig(actor_type_configs=[typeConfig1, typeConfig2])

        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))

        d = config.as_dict()
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(d['entitiesConfig'][0]['entities'], ['testactor1'])
        self.assertEqual(d['entitiesConfig'][0]['actorScanInterval'], timedelta(seconds=10))
        self.assertEqual(d['entitiesConfig'][0]['reentrancy']['enabled'], True)
        self.assertEqual(d['entitiesConfig'][0]['reentrancy']['maxStackDepth'], 32)
        self.assertEqual(d['entitiesConfig'][1]['entities'], ['testactor2'])
        self.assertEqual(d['entitiesConfig'][1]['drainOngoingCallTimeout'], timedelta(seconds=60))
        self.assertEqual(d['entitiesConfig'][1]['remindersStoragePartitions'], 10)
        self.assertNotIn('reentrancy', d['entitiesConfig'][1])
        self.assertNotIn('actorScanInterval', d['entitiesConfig'][1])
        self.assertNotIn('draingOngoingCallTimeout', d['entitiesConfig'][0])
        self.assertNotIn('remindersStoragePartitions', d['entitiesConfig'][0])
        self.assertEqual(sorted(d['entities']), ['testactor1', 'testactor2'])

    def test_update_entities(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1'])

        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, {'actortype1'})
        self.assertEqual(config._entitiesConfig, [])
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_update_entities_two_types(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1', 'actortype1'])
        self.assertEqual(config._actor_idle_timeout, timedelta(seconds=3600))
        self.assertEqual(config._actor_scan_interval, timedelta(seconds=30))
        self.assertEqual(config._drain_ongoing_call_timeout, timedelta(seconds=60))
        self.assertEqual(config._drain_rebalanced_actors, True)
        self.assertEqual(config._entities, {'actortype1', 'actortype1'})
        self.assertEqual(config._entitiesConfig, [])
        self.assertNotIn('remindersStoragePartitions', config.as_dict().keys())

    def test_update_actor_type_config(self):
        config = ActorRuntimeConfig()
        config.update_entities(['actortype1'])
        config.update_actor_type_configs(
            [ActorTypeConfig('updatetype1', actor_scan_interval=timedelta(seconds=5))]
        )

        d = config.as_dict()
        self.assertEqual(sorted(d['entities']), ['actortype1', 'updatetype1'])
        self.assertEqual(d['entitiesConfig'][0]['actorScanInterval'], timedelta(seconds=5))
        self.assertEqual(d['entitiesConfig'][0]['entities'], ['updatetype1'])
        self.assertEqual(d['actorScanInterval'], timedelta(seconds=30))

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
