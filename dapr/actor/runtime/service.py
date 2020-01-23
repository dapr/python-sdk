# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

class ActorService(object):
    """
    Represent a host for an actor type within the actor runtime
    """

    def __init__(self, actor_type_info, actor_factory = None):
        self._actor_type_info = actor_type_info
        self._actor_factory = self._default_actor_factory if actor_factory is None else actor_factory

    @property
    def actor_type_info(self):
        return self._actor_type_info

    def create_actor(self, actor_id):
        return self._actor_factory(self, actor_id)
    
    def _default_actor_factory(self, actor_service, actor_id):
        # create actor object
        return self.actor_type_info.implementation_type(actor_service, actor_id)