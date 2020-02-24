# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from datetime import timedelta
from dapr.actor.runtime.runtime_config import ActorRuntimeConfig

class ActorRuntimeConfigTests(unittest.TestCase):
    def test_default_config(self):
        config = ActorRuntimeConfig()

        self.assertEqual(config.actorIdleTimeout, timedelta(seconds=3600))
        self.assertEqual(config.actorScanInterval, timedelta(seconds=30))
        self.assertEqual(config.drainOngoingCallTimeout, timedelta(seconds=60))
        self.assertEqual(config.drainRebalancedActors, True)
        self.assertEqual(config.entities, [])
    
    def test_update_entities(self):
        config = ActorRuntimeConfig()
        config.update_entities([ 'actortype1' ])

        self.assertEqual(config.actorIdleTimeout, timedelta(seconds=3600))
        self.assertEqual(config.actorScanInterval, timedelta(seconds=30))
        self.assertEqual(config.drainOngoingCallTimeout, timedelta(seconds=60))
        self.assertEqual(config.drainRebalancedActors, True)
        self.assertEqual(config.entities, [ 'actortype1' ])
    
    def test_update_entities_two_types(self):
        config = ActorRuntimeConfig()
        config.update_entities([ 'actortype1', 'actortype1' ])

        self.assertEqual(config.actorIdleTimeout, timedelta(seconds=3600))
        self.assertEqual(config.actorScanInterval, timedelta(seconds=30))
        self.assertEqual(config.drainOngoingCallTimeout, timedelta(seconds=60))
        self.assertEqual(config.drainRebalancedActors, True)
        self.assertEqual(config.entities, [ 'actortype1', 'actortype1' ])
        
if __name__ == '__main__':
    unittest.main()
