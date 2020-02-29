# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import io
import json
import threading

from typing import Callable

from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.methodcontext import ActorMethodContext
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher
from dapr.serializers import Serializer

class ActorManager:
    """A Actor Manager manages actors of a specific actor type."""

    def __init__(self, ctx: ActorRuntimeContext):
        self._runtime_ctx = ctx
        self._active_actors = {}
        self._active_actors_lock = threading.RLock()
        self._dispatcher = ActorMethodDispatcher(ctx.actor_type_info)

    def dispatch(
            self, actor_id: ActorId,
            actor_method_name: str, request_stream: io.IOBase) -> bytes:
        if not hasattr(request_stream, 'read'):
            raise AttributeError('cannot read request stream')

        if not self._active_actors.get(actor_id.id):
            raise ValueError(f'{actor_id} is not activated')

        method_context = ActorMethodContext.create_for_actor(actor_method_name)
        arg_types = self._dispatcher.get_arg_types(actor_method_name)

        def invoke_method(actor):
            input_obj = None
            if len(arg_types) > 0:
                # read all bytes from request body bytes stream
                body_bytes = request_stream.read()
                # Limitation:
                # * Support only one argument
                # * If you use the default DaprJSONSerializer, it support only object type
                # as a argument
                input_obj = self._message_serializer.deserialize(body_bytes, arg_types[0])
                rtnval = self._dispatcher.dispatch(actor, actor_method_name, input_obj)
            else:
                rtnval = self._dispatcher.dispatch(actor, actor_method_name)
            return rtnval

        rtn_obj = self._dispatch_internal(actor_id, method_context, invoke_method)
        print(rtn_obj)
        return self._message_serializer.serialize(rtn_obj)

    def _dispatch_internal(
            self, actor_id: ActorId, method_context: ActorMethodContext,
            dispatch_action: Callable[[Actor], bytes]) -> object:
        actor = None
        with self._active_actors_lock:
            actor = self._active_actors.get(actor_id.id, None)
        if not actor:
            raise ValueError(f'{actor_id} is not activated')

        try:
            actor._on_pre_actor_method_internal(method_context)
            retval = dispatch_action(actor)
            actor._on_post_actor_method_internal(method_context)
        except Exception as e:
            actor._on_invoke_failed(e)
            # TODO: Must handle error properly
            raise e

        return retval

    @property
    def _message_serializer(self) -> Serializer:
        return self._runtime_ctx.message_serializer

    def activate_actor(self, actor_id: ActorId):
        actor = self._runtime_ctx.create_actor(actor_id)
        actor.on_activate_internal()

        with self._active_actors_lock:
            self._active_actors[actor_id.id] = actor

    def deactivate_actor(self, actor_id: ActorId):
        with self._active_actors_lock:
            deactivated_actor = self._active_actors.pop(actor_id.id, None)
            if not deactivated_actor:
                raise ValueError(f'{actor_id} is not activated')
            deactivated_actor.on_deactivate_internal()
