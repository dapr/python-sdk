# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio

from datetime import timedelta
from typing import Any, Optional

from dapr.actor.runtime.methodcontext import ActorMethodContext
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.statemanager import ActorStateManager
from dapr.actor.runtime.reminderdata import ActorReminderData
from dapr.actor.runtime.timerdata import TIMER_CALLBACK, ActorTimerData


class Actor:
    """A base class of Actors that provides the common functionality of actors.

    Example::

        class DaprActorInterface(ActorInterface):
            @actor_method(name="method")
            async def method_invoke(self, arg: str) -> str:
                ...

        class DaprActor(Actor, DaprActorInterface):
            def __init__(self, ctx, actor_id):
                super(DaprActor, self).__init__(ctx, actor_id)

            async def method_invoke(self, arg: str) -> str:
                return arg

            async def _on_activate(self):
                pass

            async def _on_deactivate(self):
                pass

    """

    def __init__(self, ctx: ActorRuntimeContext, actor_id: str):
        self.id = actor_id
        self._runtime_ctx = ctx
        self._dispatch_mapping = {}
        self._timers = {}
        self._timers_lock = asyncio.Lock()
        self._state_manager = ActorStateManager(self)

    @property
    def runtime_ctx(self) -> ActorRuntimeContext:
        return self._runtime_ctx

    async def register_reminder(
            self, name: str, state: bytes,
            due_time: timedelta, period: timedelta) -> None:
        reminder = ActorReminderData(name, state, due_time, period)
        req_body = self._runtime_ctx.message_serializer.serialize(reminder.as_dict())
        await self._runtime_ctx.dapr_client.register_reminder(
            self._runtime_ctx.actor_type_info.type_name, self.id, name, req_body)

    async def unregister_reminder(self, name: str) -> None:
        await self._runtime_ctx.dapr_client.unregister_reminder(
            self._runtime_ctx.actor_type_info.type_name, self.id, name)

    def __get_new_timer_name(self):
        return f'{self.id}_Timer_{len(self._timers) + 1}'

    async def register_timer(
            self, name: Optional[str], callback: TIMER_CALLBACK, state: Any,
            due_time: timedelta, period: timedelta) -> None:
        async with self._timers_lock:
            if name is None or name == '':
                name = self.__get_new_timer_name()
            self._timers[name] = ActorTimerData(name, callback, state, due_time, period)

        req_body = self._runtime_ctx.message_serializer.serialize(self._timers[name].as_dict())
        await self._runtime_ctx.dapr_client.register_timer(
            self._runtime_ctx.actor_type_info.type_name, self.id, name, req_body)

    async def unregister_timer(self, name: str) -> None:
        await self._runtime_ctx.dapr_client.unregister_timer(
            self._runtime_ctx.actor_type_info.type_name, self.id, name)
        async with self._timers_lock:
            self._timers.pop(name)

    async def _on_activate_internal(self) -> None:
        await self._reset_state_internal()
        await self._on_activate()
        await self._save_state_internal()

    async def _on_deactivate_internal(self) -> None:
        await self._reset_state_internal()
        await self._on_deactivate()

    async def _on_pre_actor_method_internal(self, method_context: ActorMethodContext) -> None:
        await self._on_pre_actor_method(method_context)

    async def _on_post_actor_method_internal(self, method_context: ActorMethodContext) -> None:
        await self._on_post_actor_method(method_context)
        await self._save_state_internal()

    async def _on_invoke_failed_internal(self, exception=None):
        # Exception has been thrown by user code, reset the state in state manager
        await self._reset_state_internal()

    async def _reset_state_internal(self) -> None:
        # Exception has been raised by user code, reset the state in state manager.
        await self._state_manager.clear_cache()

    async def _save_state_internal(self):
        """Saves all the state changes (add/update/remove) that were made since last call
        to the actor state provider associated with the actor.
        """
        await self._state_manager.save_state()

    async def _fire_timer_internal(self, name: str) -> None:
        timer = self._timers[name]
        return await timer.callback(timer.state)

    async def _on_activate(self) -> None:
        """Override this method to initialize the members.

        This method is called right after the actor is activated and before
        any method call or reminders are dispatched on it.
        """
        ...

    async def _on_deactivate(self) -> None:
        """Override this method to release any resources.

        This method is called when actor is deactivated (garbage collected
        by Actor Runtime). Actor operations like state changes should not
        be called from this method.
        """
        ...

    async def _on_pre_actor_method(self, method_context: ActorMethodContext) -> None:
        """Override this method for performing any action prior to
        an actor method is invoked.

        This method is invoked by actor runtime just before invoking
        an actor method.

        This method is invoked by actor runtime prior to:
            - Invoking an actor interface method when a client request comes.
            - Invoking a method when a reminder fires.
            - Invoking a timer callback when timer fires.

        :param ActorMethodContext method_context: The method information
        """
        ...

    async def _on_post_actor_method(self, method_context: ActorMethodContext) -> None:
        """Override this method for performing any action after
        an actor method has finished execution.

        This method is invoked by actor runtime an actor method has finished
        execution.

        This method is invoked by actor runtime after:
            - Invoking an actor interface method when a client request comes.
            - Invoking a method when a reminder fires.
            - Invoking a timer callback when timer fires.

        :param ActorMethodContext method_context: The method information
        """
        ...
