# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import datetime

from dapr.actor import Actor, Remindable
from examples.demo_actor.demo_actor_interface import DemoActorInterface


class DemoActor(Actor, DemoActorInterface, Remindable):
    def __init__(self, ctx, actor_id):
        super(DemoActor, self).__init__(ctx, actor_id)

    async def _on_activate(self) -> None:
        print(f'Activate {self.__class__.__name__} actor!', flush=True)

    async def _on_deactivate(self) -> None:
        print(f'Deactivate {self.__class__.__name__} actor!', flush=True)

    async def set_reminder(self, enabled) -> None:
        print(f'set reminder {enabled}', flush=True)
        if enabled == True:
            await self._register_reminder(
                'test_reminder', 'fake_state', 
                datetime.timedelta(seconds=5), datetime.timedelta(seconds=5))
        else:
            await self._unregister_reminder('test_reminder')
        print(f'set reminder {enabled}', flush=True)

    async def set_timer(self, enabled) -> None:
        print(f'set timer {enabled}', flush=True)
        if enabled == True:
            await self._register_timer(
                'test_timer', self.timer_callback, 'fake_state', 
                datetime.timedelta(seconds=5), datetime.timedelta(seconds=5))
        else:
            await self._unregister_timer('test_timer')
    
    async def timer_callback(self, obj) -> None:
        print(f'time_callback - {obj}', flush=True)

    async def receive_reminder(self, name: str, state: bytes,
                               due_time: datetime.timedelta, period: datetime.timedelta) -> None:
        print(f'{name} reminder - {state}', flush=True)

    async def get_my_data(self) -> object:
        has_value, val = await self._state_manager.try_get_state('mydata')
        print(f'has_value: {has_value}', flush=True)
        return val

    async def set_my_data(self, data) -> None:
        data['ts'] = datetime.datetime.now(datetime.timezone.utc)
        await self._state_manager.set_state('mydata', data)
        await self._state_manager.save_state()
