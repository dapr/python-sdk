# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from datetime import timedelta
from dapr.actor.runtime.actor import Actor
from dapr.actor.actor_interface import ActorInterface, actormethod
from dapr.actor.runtime.typeutils import *

class TestActorInterface(ActorInterface):
    @actormethod(name="TestMethod")
    def actor_method(self, arg):
        ...

class TestActor(Actor, TestActorInterface):
    def __init__(self):
        pass

    def actor_method(self, arg: int) -> object:
        pass

    def non_actor_method(self, arg0: int, arg1: str, arg2: float) -> object:
        pass

class TypeUtilsTests(unittest.TestCase):
    def test_get_class_method_args(self):
        args = get_class_method_args(TestActor.actor_method)
        self.assertEqual(args, ['arg'])

    def test_get_method_arg_types(self):
        arg_types = get_method_arg_types(TestActor.non_actor_method)
        self.assertEqual(arg_types, [ type(int(30)), type(str("102")), type(float(10.0)) ])

    def test_is_dapr_actor_true(self):
        self.assertTrue(is_dapr_actor(TestActor()))

    def test_is_dapr_actor_false(self):
        # Non-actor class
        class TestNonActorClass(ActorInterface):
            def test_method(self, arg: int) -> object:
                pass

        self.assertFalse(is_dapr_actor(TestNonActorClass()))

class ActorParentTests(unittest.TestCase):
    def test_get_non_actor_parent_type_returns_non_actor(self):
        pass

    def test_get_non_actor_parent_type_returns_actor(self):
        pass
