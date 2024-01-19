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
from dapr.serializers.json import DefaultJSONSerializer
import asyncio

from datetime import timedelta
from typing import Optional

from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.remindable import Remindable
from dapr.actor.actor_interface import ActorInterface, actormethod

from dapr.actor.runtime.reentrancy_context import reentrancy_ctx


# Fake Simple Actor Class for testing
class FakeSimpleActorInterface(ActorInterface):
    @actormethod(name='ActorMethod')
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

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta],
    ) -> None:
        pass


class FakeSimpleTimerActor(Actor, FakeSimpleActorInterface):
    def __init__(self, ctx, actor_id):
        super(FakeSimpleTimerActor, self).__init__(ctx, actor_id)
        self.timer_called = False

    async def actor_method(self, arg: int) -> dict:
        return {'name': 'actor_method'}

    async def timer_callback(self, obj) -> None:
        self.timer_called = True

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta],
    ) -> None:
        pass


class FakeActorCls1Interface(ActorInterface):
    # Fake Actor Class deriving multiple ActorInterfaces
    @actormethod(name='ActorCls1Method')
    async def actor_cls1_method(self, arg):
        ...

    @actormethod(name='ActorCls1Method1')
    async def actor_cls1_method1(self, arg):
        ...

    @actormethod(name='ActorCls1Method2')
    async def actor_cls1_method2(self, arg):
        ...


class FakeActorCls2Interface(ActorInterface):
    @actormethod(name='ActorCls2Method')
    async def actor_cls2_method(self, arg):
        ...

    @actormethod(name='ActionMethod')
    async def action(self, data: object) -> str:
        ...

    @actormethod(name='ActionMethodWithoutArg')
    async def action_no_arg(self) -> str:
        ...


class ReentrantActorInterface(ActorInterface):
    @actormethod(name='ReentrantMethod')
    async def reentrant_method(self, data: object) -> str:
        ...

    @actormethod(name='ReentrantMethodWithPassthrough')
    async def reentrant_pass_through_method(self, arg):
        ...


class FakeMultiInterfacesActor(
    Actor, FakeActorCls1Interface, FakeActorCls2Interface, ReentrantActorInterface
):
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

    async def reentrant_method(self, data: object) -> str:
        self.action_data = data
        return self.action_data['message']

    async def reentrant_pass_through_method(self, arg):
        pass


class FakeReentrantActor(Actor, FakeActorCls1Interface, ReentrantActorInterface):
    def __init__(self, ctx, actor_id):
        super(FakeReentrantActor, self).__init__(ctx, actor_id)

    async def reentrant_method(self, data: object) -> str:
        return reentrancy_ctx.get()

    async def reentrant_pass_through_method(self, arg):
        from dapr.actor.client import proxy

        await proxy.DaprActorHttpClient(DefaultJSONSerializer()).invoke_method(
            FakeSlowReentrantActor.__name__, 'test-id', 'ReentrantMethod'
        )

    async def actor_cls1_method(self, arg):
        pass

    async def actor_cls1_method1(self, arg):
        pass

    async def actor_cls1_method2(self, arg):
        pass


class FakeSlowReentrantActor(Actor, FakeActorCls2Interface, ReentrantActorInterface):
    def __init__(self, ctx, actor_id):
        super(FakeSlowReentrantActor, self).__init__(ctx, actor_id)

    async def reentrant_method(self, data: object) -> str:
        await asyncio.sleep(1)
        return reentrancy_ctx.get()

    async def reentrant_pass_through_method(self, arg):
        from dapr.actor.client import proxy

        await proxy.DaprActorHttpClient(DefaultJSONSerializer()).invoke_method(
            FakeReentrantActor.__name__, 'test-id', 'ReentrantMethod'
        )

    async def actor_cls2_method(self, arg):
        pass

    async def action_no_arg(self) -> str:
        pass

    async def action(self, data: object) -> str:
        pass
