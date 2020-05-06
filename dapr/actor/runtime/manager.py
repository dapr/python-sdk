# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio

from typing import Awaitable, Callable

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
        self._active_actors_lock = asyncio.Lock()
        self._dispatcher = ActorMethodDispatcher(ctx.actor_type_info)

    async def dispatch(
            self, actor_id: ActorId,
            actor_method_name: str, request_body: bytes) -> bytes:
        if not self._active_actors.get(actor_id.id):
            raise ValueError(f'{actor_id} is not activated')

        method_context = ActorMethodContext.create_for_actor(actor_method_name)
        arg_types = self._dispatcher.get_arg_types(actor_method_name)

        async def invoke_method(actor):
            if len(arg_types) > 0:
                # Limitation:
                # * Support only one argument
                # * If you use the default DaprJSONSerializer, it support only object type
                # as a argument
                input_obj = self._message_serializer.deserialize(request_body, arg_types[0])
                rtnval = await self._dispatcher.dispatch(actor, actor_method_name, input_obj)
            else:
                rtnval = await self._dispatcher.dispatch(actor, actor_method_name)
            return rtnval

        rtn_obj = await self._dispatch_internal(actor_id, method_context, invoke_method)
        return self._message_serializer.serialize(rtn_obj)

    async def _dispatch_internal(
            self, actor_id: ActorId, method_context: ActorMethodContext,
            dispatch_action: Callable[[Actor], Awaitable[bytes]]) -> object:
        actor = None
        async with self._active_actors_lock:
            actor = self._active_actors.get(actor_id.id, None)
        if not actor:
            raise ValueError(f'{actor_id} is not activated')

        try:
            await actor._on_pre_actor_method_internal(method_context)
            retval = await dispatch_action(actor)
            await actor._on_post_actor_method_internal(method_context)
        except Exception as ex:
            await actor._on_invoke_failed(ex)
            # TODO: Must handle error properly
            raise ex

        return retval

    @property
    def _message_serializer(self) -> Serializer:
        return self._runtime_ctx.message_serializer

    async def activate_actor(self, actor_id: ActorId):
        actor = self._runtime_ctx.create_actor(actor_id)
        await actor._on_activate_internal()

        async with self._active_actors_lock:
            self._active_actors[actor_id.id] = actor

    async def deactivate_actor(self, actor_id: ActorId):
        async with self._active_actors_lock:
            deactivated_actor = self._active_actors.pop(actor_id.id, None)
            if not deactivated_actor:
                raise ValueError(f'{actor_id} is not activated')
        await deactivated_actor._on_deactivate_internal()
