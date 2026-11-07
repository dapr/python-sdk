# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

import itertools
import logging
import threading
import uuid
from functools import partial
from typing import Any, Callable, Coroutine, Dict, List, Optional, Sequence

from dapr.actor.id import ActorId
from dapr.actor.runtime._method_context import ActorMethodContext
from dapr.actor.runtime._reminder_data import ActorReminderData
from dapr.actor.runtime._turn_lock import ActorTurn, ActorTurnLock
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.context import ActorRuntimeContext
from dapr.actor.runtime.method_dispatcher import ActorMethodDispatcher
from dapr.clients.exceptions import DaprInternalError
from dapr.common.reentrancy_context import reentrancy_ctx

logger = logging.getLogger(__name__)

TIMER_METHOD_NAME = 'fire_timer'
REMINDER_METHOD_NAME = 'receive_reminder'


class _ActiveActor:
    """An actor object and the daprd activation it belongs to."""

    __slots__ = ('actor', 'activation_id', 'replaced')

    def __init__(self, actor: Actor, activation_id: Optional[str]) -> None:
        self.actor = actor
        self.activation_id = activation_id
        self.replaced = False

    def mark_replaced(self) -> None:
        """Marks the object as belonging to an older activation, so it can no longer save."""
        self.replaced = True
        self.actor._state_manager._discard()


class _Admission:
    """The most recent call that arrived with an activation id for one actor ID."""

    __slots__ = ('ticket', 'activation_id', 'calls')

    def __init__(self) -> None:
        self.ticket = 0
        self.activation_id = ''
        self.calls = 0


class ActorManager:
    """A Actor Manager manages actors of a specific actor type."""

    def __init__(self, ctx: ActorRuntimeContext):
        self._runtime_ctx = ctx
        self._message_serializer = self._runtime_ctx.message_serializer

        self._turn_lock = ActorTurnLock()
        # A threading lock: calls are admitted before they wait for their turn, and the Flask
        # extension dispatches from several threads, each with its own event loop.
        self._active_actors_lock = threading.Lock()
        self._active_actors: Dict[str, _ActiveActor] = {}
        self._activating: Dict[str, _ActiveActor] = {}
        self._detached: Dict[str, List[_ActiveActor]] = {}
        self._admissions: Dict[str, _Admission] = {}
        self._tickets = itertools.count(1)

        self._dispatcher = ActorMethodDispatcher(ctx.actor_type_info)
        self._timer_method_context = ActorMethodContext.create_for_timer(TIMER_METHOD_NAME)
        self._reminder_method_context = ActorMethodContext.create_for_reminder(REMINDER_METHOD_NAME)

    async def activate_actor(self, actor_id: ActorId, activation_id: Optional[str] = None) -> Actor:
        """Activates actor, or returns it if it is already active."""
        ticket = self._admit(actor_id.id, None)
        async with self._turn_lock.turn(actor_id.id):
            await self._deactivate_detached(actor_id)
            active = await self._get_or_activate(actor_id, activation_id, ticket)
        return active.actor

    async def deactivate_actor(self, actor_id: ActorId) -> None:
        """Deactivates actor once the calls queued ahead of the deactivation finish.

        The actor is unregistered straight away, so the running call can no longer save its state.
        An activation made by a call queued ahead of the deactivation is deactivated as well.
        """
        with self._active_actors_lock:
            detached_on_arrival = self._detach(actor_id.id)
        async with self._turn_lock.turn(actor_id.id):
            with self._active_actors_lock:
                detached_in_turn = self._detach(actor_id.id)
            deactivated = [
                active for active in (detached_on_arrival, detached_in_turn) if active is not None
            ]
            await self._deactivate_detached(actor_id, deactivated)
        if not deactivated:
            raise ValueError(f'{actor_id} is not activated')

    async def fire_reminder(
        self,
        actor_id: ActorId,
        reminder_name: str,
        request_body: bytes,
        activation_id: Optional[str] = None,
    ) -> None:
        if not self._runtime_ctx.actor_type_info.is_remindable():
            raise ValueError(
                f'{self._runtime_ctx.actor_type_info.type_name} does not implment Remindable.'
            )
        request_obj = self._message_serializer.deserialize(request_body, object)
        if not isinstance(request_obj, dict):
            # ignore if request_obj is not dict
            return
        reminder_data = ActorReminderData.from_dict(reminder_name, request_obj)

        async def invoke_reminder(actor: Actor) -> Optional[bytes]:
            reminder = getattr(actor, REMINDER_METHOD_NAME)
            if reminder is not None:
                await reminder(
                    reminder_data.reminder_name,
                    reminder_data.state,
                    reminder_data.due_time,
                    reminder_data.period,
                    reminder_data.ttl,
                )
            return None

        await self._dispatch_internal(
            actor_id, self._reminder_method_context, invoke_reminder, activation_id
        )

    async def fire_timer(
        self,
        actor_id: ActorId,
        timer_name: str,
        request_body: bytes,
        activation_id: Optional[str] = None,
    ) -> None:
        timer = self._message_serializer.deserialize(request_body, object)

        async def invoke_timer(actor: Actor) -> Optional[bytes]:
            await actor._fire_timer_internal(timer['callback'], timer['data'])
            return None

        await self._dispatch_internal(
            actor_id, self._timer_method_context, invoke_timer, activation_id
        )

    async def dispatch(
        self,
        actor_id: ActorId,
        actor_method_name: str,
        request_body: bytes,
        activation_id: Optional[str] = None,
        reentrancy_id: Optional[str] = None,
    ) -> bytes:
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

        rtn_obj = await self._dispatch_internal(
            actor_id, method_context, invoke_method, activation_id, reentrancy_id
        )
        return self._message_serializer.serialize(rtn_obj)

    async def _dispatch_internal(
        self,
        actor_id: ActorId,
        method_context: ActorMethodContext,
        dispatch_action: Callable[[Actor], Coroutine[Any, Any, Optional[bytes]]],
        activation_id: Optional[str] = None,
        reentrancy_id: Optional[str] = None,
    ) -> object:
        in_chain = self._turn_lock.is_in_chain(actor_id.id, reentrancy_id)
        admitted_id = None if in_chain else activation_id
        ticket = self._admit(actor_id.id, admitted_id)
        try:
            async with self._turn_lock.turn(actor_id.id, reentrancy_id) as turn:
                active = await self._enter_turn(actor_id, activation_id, ticket, turn)
                turn.allow_reentrancy()
                return await self._invoke(actor_id, active.actor, method_context, dispatch_action)
        finally:
            self._release_admission(actor_id.id, admitted_id)

    async def _invoke(
        self,
        actor_id: ActorId,
        actor: Actor,
        method_context: ActorMethodContext,
        dispatch_action: Callable[[Actor], Coroutine[Any, Any, Optional[bytes]]],
    ) -> object:
        try:
            if reentrancy_ctx.get(None) is not None:
                actor._state_manager.set_state_context(str(uuid.uuid4()))
            await actor._on_pre_actor_method_internal(method_context)
            retval = await dispatch_action(actor)
            await actor._on_post_actor_method_internal(
                method_context, partial(self._ensure_still_registered, actor_id, actor)
            )
        except DaprInternalError as ex:
            await actor._on_invoke_failed_internal(ex)
            raise ex
        finally:
            if reentrancy_ctx is not None:
                actor._state_manager.set_state_context(None)

        return retval

    async def _enter_turn(
        self,
        actor_id: ActorId,
        activation_id: Optional[str],
        ticket: int,
        turn: ActorTurn,
    ) -> _ActiveActor:
        if not turn.reentered:
            await self._deactivate_detached(actor_id)
            return await self._get_or_activate(actor_id, activation_id, ticket)
        # A reentrant call runs inside its chain's turn, so it never starts an activation.
        with self._active_actors_lock:
            active = self._active_actors.get(actor_id.id)
        if active is None:
            raise DaprInternalError(
                f'{actor_id} was deactivated or replaced during this call chain, '
                'the call was not run'
            )
        return active

    async def _get_or_activate(
        self, actor_id: ActorId, activation_id: Optional[str], ticket: int
    ) -> _ActiveActor:
        with self._active_actors_lock:
            self._raise_if_superseded(actor_id, activation_id, ticket)
            if activation_id:
                self._replace_stale(actor_id.id, activation_id)
            registered = self._active_actors.get(actor_id.id)
        if registered is not None:
            return registered
        await self._deactivate_detached(actor_id)
        return await self._activate_in_turn(actor_id, activation_id, ticket)

    async def _activate_in_turn(
        self, actor_id: ActorId, activation_id: Optional[str], ticket: int
    ) -> _ActiveActor:
        actor = self._runtime_ctx.create_actor(actor_id)
        active = _ActiveActor(actor, activation_id or None)
        with self._active_actors_lock:
            self._raise_if_superseded(actor_id, activation_id, ticket)
            self._activating[actor_id.id] = active
        try:
            await actor._on_activate_internal(lambda: not active.replaced)
        finally:
            with self._active_actors_lock:
                self._activating.pop(actor_id.id, None)

        with self._active_actors_lock:
            replaced = active.replaced or self._is_superseded(actor_id.id, activation_id, ticket)
            if not replaced:
                self._active_actors[actor_id.id] = active
        if replaced:
            await self._deactivate_discarded(actor_id, actor)
            raise DaprInternalError(
                f'{actor_id} was replaced by a newer activation during this activation'
            )
        return active

    def _admit(self, actor_key: str, activation_id: Optional[str]) -> int:
        """Numbers the call; a new activation id replaces the stale object before waiting."""
        with self._active_actors_lock:
            ticket = next(self._tickets)
            if not activation_id:
                return ticket
            admission = self._admissions.setdefault(actor_key, _Admission())
            admission.ticket = ticket
            admission.activation_id = activation_id
            admission.calls += 1
            self._replace_stale(actor_key, activation_id)
            return ticket

    def _release_admission(self, actor_key: str, activation_id: Optional[str]) -> None:
        if not activation_id:
            return
        with self._active_actors_lock:
            admission = self._admissions[actor_key]
            admission.calls -= 1
            if admission.calls == 0:
                del self._admissions[actor_key]

    def _is_superseded(self, actor_key: str, activation_id: Optional[str], ticket: int) -> bool:
        """Activation ids are not ordered, so a different id that arrived later is the newer one."""
        if not activation_id:
            return False
        admission = self._admissions.get(actor_key)
        return (
            admission is not None
            and admission.ticket > ticket
            and admission.activation_id != activation_id
        )

    def _raise_if_superseded(
        self, actor_id: ActorId, activation_id: Optional[str], ticket: int
    ) -> None:
        if self._is_superseded(actor_id.id, activation_id, ticket):
            raise DaprInternalError(
                f'{actor_id} was activated by a newer activation while this call waited, '
                'the call was not run'
            )

    def _replace_stale(self, actor_key: str, activation_id: str) -> None:
        """Replaces every object of another activation; the registered one is also detached."""
        pending = self._activating.get(actor_key)
        if pending is not None and pending.activation_id != activation_id:
            pending.mark_replaced()
        for detached in self._detached.get(actor_key, []):
            if detached.activation_id != activation_id:
                detached.mark_replaced()
        registered = self._active_actors.get(actor_key)
        if registered is None or registered.activation_id == activation_id:
            return
        registered.mark_replaced()
        self._detach(actor_key)

    def _detach(self, actor_key: str) -> Optional[_ActiveActor]:
        detached = self._active_actors.pop(actor_key, None)
        if detached is not None:
            self._detached.setdefault(actor_key, []).append(detached)
        return detached

    async def _deactivate_detached(
        self, actor_id: ActorId, owned: Sequence[_ActiveActor] = ()
    ) -> None:
        """Deactivates objects detached since the last turn, raising only for ``owned`` ones."""
        with self._active_actors_lock:
            detached = self._detached.pop(actor_id.id, [])
        owned_error: Optional[Exception] = None
        for active in detached:
            try:
                await active.actor._on_deactivate_internal()
            except Exception as exception:  # noqa: BLE001
                if active in owned and not active.replaced:
                    owned_error = exception
                    continue
                logger.exception('Deactivating detached object for %s failed', actor_id)
        if owned_error is not None:
            raise owned_error

    def _ensure_still_registered(self, actor_id: ActorId, actor: Actor) -> None:
        active = self._active_actors.get(actor_id.id)
        if active is None or active.actor is not actor:
            raise DaprInternalError(
                f'{actor_id} was deactivated or replaced during the call, state not saved'
            )

    async def _deactivate_discarded(self, actor_id: ActorId, actor: Actor) -> None:
        """Logs instead of raising so the unrelated call does not fail."""
        actor._state_manager._discard()
        try:
            await actor._on_deactivate_internal()
        except Exception:  # noqa: BLE001
            logger.exception('Deactivating discarded object for %s failed', actor_id)
