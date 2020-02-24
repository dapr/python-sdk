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
    @actormethod(name="ActorMethod")
    def actor_method(self, arg: int) -> dict:
        ...

class TestActor(Actor, TestActorInterface):
    def __init__(self, ctx, actor_id):
        super(TestActor, self).__init__(ctx, actor_id)

    def actor_method(self, arg: int) -> dict:
        return { 'name': 'actor_method' }

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
    def __init__(self, ctx, actor_id):
        super(TestActorImpl, self).__init__(ctx, actor_id)

    def actor_cls1_method(self, arg): pass
    def actor_cls1_method1(self, arg): pass
    def actor_cls1_method2(self, arg): pass
    def actor_cls2_method(self, arg): pass

# Test Actors for ActorManager test
class ManagerTestActorInterface(ActorInterface):
    @actormethod(name="ActionMethod")
    def action(self, data: object) -> str:
        ...

class ManagerTestActor(Actor, ManagerTestActorInterface):
    def __init__(self, ctx, actor_id):
        super(ManagerTestActor, self).__init__(ctx, actor_id)
        self.activated = False
        self.deactivated = False
        self.id = actor_id
    
    def action(self, data: object) -> str:
        self.action_data = data
        return data['message']

    def _on_activate(self):
        self.activated = True
        self.deactivated = False

    def _on_deactivate(self):
        self.activated = False
        self.deactivated = True