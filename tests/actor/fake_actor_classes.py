# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from datetime import timedelta

from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.remindable import Remindable
from dapr.actor.actor_interface import ActorInterface, actormethod


# Fake Simple Actor Class for testing
class FakeSimpleActorInterface(ActorInterface):
    @actormethod(name="ActorMethod")
    async def actor_method(self, arg: int) -> dict:
        ...


class FakeSimpleActor(Actor, FakeSimpleActorInterface):
    def __init__(self, ctx, actor_id):
        super(FakeSimpleActor, self).__init__(ctx, actor_id)

    async def actor_method(self, arg: int) -> dict:
        return {'name': 'actor_method'}

    async def non_actor_method(self, arg0: int, arg1: str, arg2: float) -> str:
        pass


class FakeSimpleReminderActor(Actor, FakeSimpleActorInterface, Remindable):
    def __init__(self, ctx, actor_id):
        super(FakeSimpleReminderActor, self).__init__(ctx, actor_id)

    async def actor_method(self, arg: int) -> dict:
        return {'name': 'actor_method'}

    async def non_actor_method(self, arg0: int, arg1: str, arg2: float) -> str:
        pass

    async def receive_reminder(self, name: str, state: bytes,
                               due_time: timedelta, period: timedelta) -> None:
        pass


class FakeSimpleTimerActor(Actor, FakeSimpleActorInterface):
    def __init__(self, ctx, actor_id):
        super(FakeSimpleTimerActor, self).__init__(ctx, actor_id)
        self.timer_called = False

    async def actor_method(self, arg: int) -> dict:
        return {'name': 'actor_method'}

    async def timer_callback(self, obj) -> None:
        self.timer_called = True

    async def receive_reminder(self, name: str, state: bytes,
                               due_time: timedelta, period: timedelta) -> None:
        pass


class FakeActorCls1Interface(ActorInterface):
    # Fake Actor Class deriving multiple ActorInterfaces
    @actormethod(name="ActorCls1Method")
    async def actor_cls1_method(self, arg):
        ...

    @actormethod(name="ActorCls1Method1")
    async def actor_cls1_method1(self, arg):
        ...

    @actormethod(name="ActorCls1Method2")
    async def actor_cls1_method2(self, arg):
        ...


class FakeActorCls2Interface(ActorInterface):
    @actormethod(name="ActorCls2Method")
    async def actor_cls2_method(self, arg):
        ...

    @actormethod(name="ActionMethod")
    async def action(self, data: object) -> str:
        ...

    @actormethod(name="ActionMethodWithoutArg")
    async def action_no_arg(self) -> str:
        ...


class FakeMultiInterfacesActor(Actor, FakeActorCls1Interface, FakeActorCls2Interface):
    def __init__(self, ctx, actor_id):
        super(FakeMultiInterfacesActor, self).__init__(ctx, actor_id)
        self.activated = False
        self.deactivated = False
        self.id = actor_id

    async def actor_cls1_method(self, arg):
        pass

    async def actor_cls1_method1(self, arg):
        pass

    async def actor_cls1_method2(self, arg):
        pass

    async def actor_cls2_method(self, arg):
        pass

    async def action(self, data: object) -> str:
        self.action_data = data
        return self.action_data['message']

    async def action_no_arg(self) -> str:
        self.action_data = {'message': 'no_arg'}
        return self.action_data['message']

    async def _on_activate(self):
        self.activated = True
        self.deactivated = False

    async def _on_deactivate(self):
        self.activated = False
        self.deactivated = True
