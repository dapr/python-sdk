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

import asyncio
import uuid

from typing import Any, Callable, Coroutine, Dict, Optional

from dapr.actor.id import ActorId
from dapr.clients.exceptions import DaprInternalError
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime._method_context import ActorMethodContext
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher
from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime.reentrancy_context import reentrancy_ctx

TIMER_METHOD_NAME = 'fire_timer'
REMINDER_METHOD_NAME = 'receive_reminder'


class ActorManager:
    """A Actor Manager manages actors of a specific actor type."""

    def __init__(self, ctx: ActorRuntimeContext):
        self._runtime_ctx = ctx
        self._message_serializer = self._runtime_ctx.message_serializer

        self._active_actors: Dict[str, Actor] = {}
        self._active_actors_lock = asyncio.Lock()

        self._dispatcher = ActorMethodDispatcher(ctx.actor_type_info)
        self._timer_method_context = ActorMethodContext.create_for_timer(TIMER_METHOD_NAME)
        self._reminder_method_context = ActorMethodContext.create_for_reminder(REMINDER_METHOD_NAME)

    async def activate_actor(self, actor_id: ActorId):
        """Activates actor."""
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

    async def fire_reminder(
            self, actor_id: ActorId,
            reminder_name: str, request_body: bytes) -> None:
        if not self._runtime_ctx.actor_type_info.is_remindable():
            raise ValueError(
                f'{self._runtime_ctx.actor_type_info.type_name} does not implment Remindable.')
        request_obj = self._message_serializer.deserialize(request_body, object)
        if isinstance(request_obj, dict):
            reminder_data = ActorReminderData.from_dict(reminder_name, request_obj)
        # ignore if request_obj is not dict

        async def invoke_reminder(actor: Actor) -> Optional[bytes]:
            reminder = getattr(actor, REMINDER_METHOD_NAME)
            if reminder is not None:
                await reminder(reminder_data.reminder_name, reminder_data.state,
                               reminder_data.due_time, reminder_data.period, reminder_data.ttl)
            return None

        await self._dispatch_internal(actor_id, self._reminder_method_context, invoke_reminder)

    async def fire_timer(
            self, actor_id: ActorId,
            timer_name: str, request_body: bytes) -> None:
        timer = self._message_serializer.deserialize(request_body, object)

        async def invoke_timer(actor: Actor) -> Optional[bytes]:
            await actor._fire_timer_internal(timer['callback'], timer['data'])
            return None

        await self._dispatch_internal(actor_id, self._timer_method_context, invoke_timer)

    async def dispatch(
            self, actor_id: ActorId,
            actor_method_name: str, request_body: bytes) -> bytes:
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
            dispatch_action: Callable[[Actor], Coroutine[Any, Any, Optional[bytes]]]) -> object:
        # Activate actor when actor is invoked.
        if actor_id.id not in self._active_actors:
            await self.activate_actor(actor_id)
        actor = None
        async with self._active_actors_lock:
            actor = self._active_actors.get(actor_id.id, None)
        if not actor:
            raise ValueError(f'{actor_id} is not activated')

        try:
            if reentrancy_ctx.get(None) is not None:
                actor._state_manager.set_state_context(str(uuid.uuid4()))
            await actor._on_pre_actor_method_internal(method_context)
            retval = await dispatch_action(actor)
            await actor._on_post_actor_method_internal(method_context)
        except DaprInternalError as ex:
            await actor._on_invoke_failed_internal(ex)
            raise ex
        finally:
            if reentrancy_ctx is not None:
                actor._state_manager.set_state_context(None)

        return retval
