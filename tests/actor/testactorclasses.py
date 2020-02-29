# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio
import unittest

from dapr.actor.runtime.actor import Actor
from dapr.actor.actor_interface import ActorInterface, actormethod

# Classes for testing
class TestActorInterface(ActorInterface):
    @actormethod(name="ActorMethod")
    async def actor_method(self, arg: int) -> dict:
        ...

class TestActor(Actor, TestActorInterface):
    def __init__(self, ctx, actor_id):
        super(TestActor, self).__init__(ctx, actor_id)

    async def actor_method(self, arg: int) -> dict:
        return { 'name': 'actor_method' }

    async def non_actor_method(self, arg0: int, arg1: str, arg2: float) -> str:
        pass

class TestActorCls1Interface(ActorInterface):
    @actormethod(name="ActorCls1Method")
    async def actor_cls1_method(self, arg): ...

    @actormethod(name="ActorCls1Method1")
    async def actor_cls1_method1(self, arg): ...
    
    @actormethod(name="ActorCls1Method2")
    async def actor_cls1_method2(self, arg): ...

class TestActorCls2Interface(ActorInterface):
    @actormethod(name="ActorCls2Method")
    async def actor_cls2_method(self, arg): ...

class TestActorImpl(Actor, TestActorCls1Interface, TestActorCls2Interface):
    def __init__(self, ctx, actor_id):
        super(TestActorImpl, self).__init__(ctx, actor_id)

    async def actor_cls1_method(self, arg): pass
    async def actor_cls1_method1(self, arg): pass
    async def actor_cls1_method2(self, arg): pass
    async def actor_cls2_method(self, arg): pass

# Test Actors for ActorManager test
class ManagerTestActorInterface(ActorInterface):
    @actormethod(name="ActionMethod")
    async def action(self, data: object) -> str:
        ...

class ManagerTestActor(Actor, ManagerTestActorInterface):
    def __init__(self, ctx, actor_id):
        super(ManagerTestActor, self).__init__(ctx, actor_id)
        self.activated = False
        self.deactivated = False
        self.id = actor_id
    
    async def action(self, data: object) -> str:
        self.action_data = data
        return data['message']

    async def _on_activate(self):
        self.activated = True
        self.deactivated = False

    async def _on_deactivate(self):
        self.activated = False
        self.deactivated = True