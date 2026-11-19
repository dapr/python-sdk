# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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
import threading
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator, Deque, Dict, Optional, Tuple


def _resolve(future: 'asyncio.Future[None]') -> None:
    if not future.done():
        future.set_result(None)


class _Waiter:
    __slots__ = ('loop', 'future', 'reentrancy_id', 'granted', 'reentered')

    def __init__(self, reentrancy_id: Optional[str]) -> None:
        self.loop = asyncio.get_running_loop()
        self.future: 'asyncio.Future[None]' = self.loop.create_future()
        self.reentrancy_id = reentrancy_id
        self.granted = False
        self.reentered = False


class _TurnEntry:
    __slots__ = ('active_calls', 'reentrancy_id', 'reentrancy_allowed', 'waiters')

    def __init__(self) -> None:
        self.active_calls = 0
        self.reentrancy_id: Optional[str] = None
        self.reentrancy_allowed = False
        self.waiters: Deque[_Waiter] = deque()


class ActorTurn:
    """A turn held by one call on one actor ID."""

    def __init__(self, lock: 'ActorTurnLock', entry: _TurnEntry, reentered: bool) -> None:
        self._lock = lock
        self._entry = entry
        self.reentered = reentered

    def allow_reentrancy(self) -> None:
        """Lets calls with this turn's reentrancy ID enter; called once activation is done."""
        self._lock._allow_reentrancy(self._entry)


class ActorTurnLock:
    """Runs one turn at a time per actor ID, in arrival order.

    Waiters may come from different threads and event loops (the Flask extension runs each
    callback in its own loop), so a waiter is woken with ``call_soon_threadsafe`` on its own loop.
    """

    def __init__(self) -> None:
        self._sync = threading.Lock()
        self._entries: Dict[str, _TurnEntry] = {}

    @asynccontextmanager
    async def turn(
        self, actor_id: str, reentrancy_id: Optional[str] = None
    ) -> AsyncIterator[ActorTurn]:
        """Holds the actor's turn while the body runs, releasing it on every outcome.

        A call whose reentrancy ID matches the running turn enters it once the turn allows
        reentrancy, without queueing behind other callers.
        """
        entry, reentered = await self._acquire(actor_id, reentrancy_id or None)
        try:
            yield ActorTurn(self, entry, reentered)
        finally:
            with self._sync:
                self._release(actor_id, entry)

    def is_in_chain(self, actor_id: str, reentrancy_id: Optional[str]) -> bool:
        """Returns whether a turn of this reentrancy chain is running for the actor."""
        if not reentrancy_id:
            return False
        with self._sync:
            entry = self._entries.get(actor_id)
            return (
                entry is not None
                and entry.active_calls > 0
                and entry.reentrancy_id == reentrancy_id
            )

    async def _acquire(
        self, actor_id: str, reentrancy_id: Optional[str]
    ) -> Tuple[_TurnEntry, bool]:
        with self._sync:
            entry = self._entries.setdefault(actor_id, _TurnEntry())
            if entry.active_calls == 0:
                self._start_turn(entry, reentrancy_id)
                return entry, False
            if (
                reentrancy_id is not None
                and entry.reentrancy_allowed
                and entry.reentrancy_id == reentrancy_id
            ):
                entry.active_calls += 1
                return entry, True
            waiter = _Waiter(reentrancy_id)
            entry.waiters.append(waiter)

        try:
            await waiter.future
        except BaseException:
            with self._sync:
                if waiter.granted:
                    self._release(actor_id, entry)
                else:
                    entry.waiters.remove(waiter)
                    self._remove_if_idle(actor_id, entry)
            raise
        return entry, waiter.reentered

    def _allow_reentrancy(self, entry: _TurnEntry) -> None:
        with self._sync:
            if entry.reentrancy_allowed or entry.reentrancy_id is None:
                return
            entry.reentrancy_allowed = True
            chained = [
                queued for queued in entry.waiters if queued.reentrancy_id == entry.reentrancy_id
            ]
            for waiter in chained:
                entry.waiters.remove(waiter)
                waiter.reentered = True
                if self._grant(waiter):
                    entry.active_calls += 1

    def _release(self, actor_id: str, entry: _TurnEntry) -> None:
        entry.active_calls -= 1
        if entry.active_calls > 0:
            return
        while entry.waiters:
            waiter = entry.waiters.popleft()
            self._start_turn(entry, waiter.reentrancy_id)
            if self._grant(waiter):
                return
        entry.active_calls = 0
        self._remove_if_idle(actor_id, entry)

    def _remove_if_idle(self, actor_id: str, entry: _TurnEntry) -> None:
        if entry.active_calls or entry.waiters or self._entries.get(actor_id) is not entry:
            return
        del self._entries[actor_id]

    @staticmethod
    def _start_turn(entry: _TurnEntry, reentrancy_id: Optional[str]) -> None:
        entry.active_calls = 1
        entry.reentrancy_id = reentrancy_id
        entry.reentrancy_allowed = False

    @staticmethod
    def _grant(waiter: _Waiter) -> bool:
        waiter.granted = True
        try:
            waiter.loop.call_soon_threadsafe(_resolve, waiter.future)
        except RuntimeError:
            # The waiter's event loop is closed, so nobody is left to take the turn.
            waiter.granted = False
            return False
        return True
