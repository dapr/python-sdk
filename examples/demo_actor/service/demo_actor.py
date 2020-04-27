# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import datetime

from dapr.actor import Actor
from examples.demo_actor.demo_actor_interface import DemoActorInterface, actormethod

class DemoActor(Actor, DemoActorInterface):
    def __init__(self, ctx, actor_id):
        super(DemoActor, self).__init__(ctx, actor_id)
    
    async def _on_activate(self):
        print (f'Activate {self.__class__.__name__} actor!', flush=True)

    async def _on_deactivate(self):
        print (f'Deactivate {self.__class__.__name__} actor!', flush=True)

    async def get_my_data(self) -> object:
        has_value, val = await self._state_manager.try_get_state('mydata')
        print (f'has_value: {has_value}', flush=True)
        return val

    async def set_my_data(self, data) -> None:
        data['ts'] = datetime.datetime.now(datetime.timezone.utc)
        await self._state_manager.set_state('mydata', data)
        await self._state_manager.save_state()
