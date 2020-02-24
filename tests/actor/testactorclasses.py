# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from dapr.actor.runtime.actor import Actor
from dapr.actor.actor_interface import ActorInterface, actormethod

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
