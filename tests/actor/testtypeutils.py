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

# Classes for testing
class TestActorInterface(ActorInterface):
    @actormethod(name="TestMethod")
    def actor_method(self, arg):
        ...

class TestActor(Actor, TestActorInterface):
    def __init__(self):
        pass

    def actor_method(self, arg: int) -> object:
        pass

    def non_actor_method(self, arg0: int, arg1: str, arg2: float) -> str:
        pass

class TestActorCls1Interface(ActorInterface):
    @actormethod(name="ActorCls1Method")
    def actor_cls1_method(self, arg): ...

    @actormethod(name="ActorCls1Method1")
    def actor_cls1_method1(self, arg): ...
    
    @actormethod(name="ActorCls1Method2")
    def actor_cls1_method2(self, arg): ...

class TestActorCls2Interface(ActorInterface):
    @actormethod(name="ActorCls2Method")
    def actor_cls2_method(self, arg): ...

class TestActorImpl(Actor, TestActorCls1Interface, TestActorCls2Interface):
    def actor_cls1_method(self, arg): pass
    def actor_cls1_method1(self, arg): pass
    def actor_cls1_method2(self, arg): pass
    def actor_cls2_method(self, arg): pass


class TypeUtilsTests(unittest.TestCase):
    def test_get_class_method_args(self):
        args = get_class_method_args(TestActor.actor_method)
        self.assertEqual(args, ['arg'])

    def test_get_method_arg_types(self):
        arg_types = get_method_arg_types(TestActor.non_actor_method)
        self.assertEqual(arg_types, [ type(int(30)), type(str("102")), type(float(10.0)) ])

    def test_get_return_types(self):
        rtn_type = get_method_return_types(TestActor.actor_method)
        self.assertEqual(object, rtn_type)

        rtn_type = get_method_return_types(TestActor.non_actor_method)
        self.assertEqual(str, rtn_type)

    def test_is_dapr_actor_true(self):
        self.assertTrue(is_dapr_actor(TestActor))

    def test_is_dapr_actor_false(self):
        # Non-actor class
        class TestNonActorClass(ActorInterface):
            def test_method(self, arg: int) -> object:
                pass

        self.assertFalse(is_dapr_actor(TestNonActorClass))
    
    def test_get_actor_interface(self):
        actor_interfaces = get_actor_interfaces(TestActorImpl)

        self.assertEqual(TestActorCls1Interface, actor_interfaces[0])
        self.assertEqual(TestActorCls2Interface, actor_interfaces[1])

    def test_get_dispatchable_attrs(self):
        dispatchable_attrs = get_dispatchable_attrs(TestActorImpl)
        expected_dispatchable_attrs = [
            'ActorCls1Method',
            'ActorCls1Method1',
            'ActorCls1Method1',
            'ActorCls2Method'
        ]

        method_cnt = 0
        for method in expected_dispatchable_attrs:
            if dispatchable_attrs.get(method) is not None:
                method_cnt = method_cnt + 1
        
        self.assertEqual(len(expected_dispatchable_attrs), method_cnt)
