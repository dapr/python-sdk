# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dapr.actor import Actor
from examples.demo_actor.demo_actor_interface import DemoActorInterface, actormethod

class DemoActor(Actor, DemoActorInterface):
    def __init__(self, ctx, actor_id):
        super(DemoActor, self).__init__(ctx, actor_id)

        # Set default data
        self._mydata = {
            "data": "default"
        }
    
    async def _on_activate(self):
        print (f'Activate {self.__class__.__name__} actor!', flush=True)

    async def _on_deactivate(self):
        print (f'Deactivate {self.__class__.__name__} actor!', flush=True)

    async def get_my_data(self) -> object:
        return self._mydata

    async def set_my_data(self, data) -> None:
        self._mydata = data
