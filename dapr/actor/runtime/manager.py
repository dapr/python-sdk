# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import json
import threading

from dapr.actor import ActorId
from dapr.actor.runtime.service import ActorService

class ActorManager:
    """A Actor Manager manages actors of a specific actor type."""

    def __init__(self, actor_service: ActorService):
        self._actor_service = actor_service
        self._active_actors = {}
        self._active_actors_lock = threading.RLock()

    def dispatch(self, actor_id: ActorId,
            actor_method_name: str, request_stream) -> bytes:
        body_bytes = request_stream.read()
        input_obj = self._message_serializer.deserialize(body_bytes)
        rtn_obj = self._active_actors[actor_id].dispatch_method(actor_method_name, input_obj)
        return self._message_serializer.serialize(rtn_obj)

    @property
    def _message_serializer(self):
        return self._actor_service.message_serializer

    def activate_actor(self, actor_id: ActorId):
        actor = self._actor_service.create_actor(actor_id)
        actor.on_activate_internal()

        with self._active_actors_lock:
            self._active_actors[actor_id] = actor

    def deactivate_actor(self, actor_id: ActorId):
        with self._active_actors_lock:
            deactivated_actor = self._active_actors.pop(actor_id, None)
            deactivated_actor.on_deactivate_internal()
