# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dapr.actor.actor_interface import ActorInterface, actormethod

class DemoActorInterface(ActorInterface):
    @actormethod(name="GetMyData")
    def get_my_data(self) -> object: ...
    
    @actormethod(name="SetMyData")
    def set_my_data(self, data: object) -> None: ...
