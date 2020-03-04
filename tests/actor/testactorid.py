# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from dapr.actor.id import ActorId

class ActorIdTests(unittest.TestCase):
    def test_create_actor_id(self):
        actor_id_1 = ActorId('1')
        self.assertEqual('1', actor_id_1.id)
    
    def test_create_random_id(self):
        actor_id_random = ActorId.create_random_id()
        self.assertEqual(len('f56d5aec5b3b11ea9121acde48001122'), len(actor_id_random.id))
    
    def test_get_hash(self):
        actor_test_id = ActorId('testId')
        self.assertIsNotNone(actor_test_id.__hash__)
    
    def test_comparison(self):
        actor_id_1 = ActorId('1')
        actor_id_1a = ActorId('1')
        self.assertTrue(actor_id_1 == actor_id_1a)

        actor_id_2 = ActorId('2')
        self.assertFalse(actor_id_1 == actor_id_2)
