# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import json
import threading

from typing import Callable

from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.methodcontext import ActorMethodContext
from dapr.actor.runtime.service import ActorService
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher
from dapr.serializers import Serializer

class ActorManager:
    """A Actor Manager manages actors of a specific actor type."""

    def __init__(self, actor_service: ActorService):
        self._actor_service = actor_service
        self._active_actors = {}
        self._active_actors_lock = threading.RLock()
        self._dispatcher = ActorMethodDispatcher(actor_service.actor_type_info)

    def dispatch(
            self, actor_id: ActorId,
            actor_method_name: str, request_stream) -> bytes:
        method_context = ActorMethodContext.create_for_actor(actor_method_name)
        # params = self._dispatcher.get_params(actor_method_name)

        def invoke_method(actor):
            body_bytes = request_stream.read()
            # TODO: deserialize body_bytes to params
            input_obj = self._message_serializer.deserialize(body_bytes)
            return self._dispatcher.dispatch(self._active_actors[actor_id], actor_method_name, input_obj)

        rtn_obj = self._dispatch_internal(actor_id, method_context, invoke_method)
        return self._message_serializer.serialize(rtn_obj)

    def _dispatch_internal(
            self, actor_id: ActorId, method_context: ActorMethodContext,
            dispatch_action: Callable[[Actor], bytes]) -> object:
        actor = None
        with self._active_actors_lock:
            actor = self._active_actors.get(actor_id, None)
        if not actor:
            raise ValueError(f'{actor_id} is not yet activated')

        try:
            actor.on_pre_actor_method_internal(method_context)
            retval = dispatch_action(actor)
            actor.on_post_actor_method_internal(method_context)
        except Exception as e:
            actor.on_invoke_failed(e)
            raise e

        return retval

    @property
    def _message_serializer(self) -> Serializer:
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
