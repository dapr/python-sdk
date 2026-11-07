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
import unittest
from typing import List, Optional, Tuple

from dapr.actor.runtime._turn_lock import ActorTurnLock, _Waiter
from tests.actor.utils import _let_pending_tasks_run

WAIT_SECONDS = 5


class ActorTurnLockTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._lock = ActorTurnLock()

    async def _hold(
        self,
        entered: asyncio.Event,
        release: asyncio.Event,
        actor_id: str,
        reentrancy_id: Optional[str],
        allow_reentrancy: bool,
    ) -> None:
        async with self._lock.turn(actor_id, reentrancy_id) as turn:
            if allow_reentrancy:
                turn.allow_reentrancy()
            entered.set()
            await release.wait()

    async def _start_holding(
        self,
        actor_id: str = 'a',
        reentrancy_id: Optional[str] = None,
        allow_reentrancy: bool = False,
    ) -> Tuple['asyncio.Task[None]', asyncio.Event]:
        entered = asyncio.Event()
        release = asyncio.Event()
        holder = asyncio.ensure_future(
            self._hold(entered, release, actor_id, reentrancy_id, allow_reentrancy)
        )
        await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
        return holder, release

    async def _record(
        self,
        order: List[str],
        name: str,
        actor_id: str = 'a',
        reentrancy_id: Optional[str] = None,
    ) -> bool:
        async with self._lock.turn(actor_id, reentrancy_id) as turn:
            order.append(name)
            return turn.reentered

    async def test_turns_for_one_actor_run_one_at_a_time(self):
        holder, release = await self._start_holding()
        order: List[str] = []
        waiter = asyncio.ensure_future(self._record(order, 'second'))
        await _let_pending_tasks_run()

        self.assertEqual([], order)

        release.set()
        await asyncio.wait_for(asyncio.gather(holder, waiter), WAIT_SECONDS)
        self.assertEqual(['second'], order)
        self.assertEqual({}, self._lock._entries)

    async def test_turns_for_different_actors_run_in_parallel(self):
        holder, release = await self._start_holding('a')
        order: List[str] = []

        await asyncio.wait_for(self._record(order, 'b', actor_id='b'), WAIT_SECONDS)

        self.assertEqual(['b'], order)
        release.set()
        await asyncio.wait_for(holder, WAIT_SECONDS)

    async def test_waiters_enter_in_arrival_order(self):
        holder, release = await self._start_holding()
        order: List[str] = []
        names = ['first', 'second', 'third']
        waiters = [asyncio.ensure_future(self._record(order, name)) for name in names]
        await _let_pending_tasks_run()

        release.set()
        await asyncio.wait_for(asyncio.gather(holder, *waiters), WAIT_SECONDS)

        self.assertEqual(names, order)

    async def test_waiter_cancelled_while_queued_leaves_the_queue(self):
        holder, release = await self._start_holding()
        order: List[str] = []
        cancelled = asyncio.ensure_future(self._record(order, 'cancelled'))
        waiter = asyncio.ensure_future(self._record(order, 'next'))
        await _let_pending_tasks_run()

        cancelled.cancel()
        await _let_pending_tasks_run()
        release.set()
        await asyncio.wait_for(asyncio.gather(holder, waiter), WAIT_SECONDS)

        self.assertTrue(cancelled.cancelled())
        self.assertEqual(['next'], order)
        self.assertEqual({}, self._lock._entries)

    async def test_waiter_cancelled_after_its_grant_passes_the_turn_on(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        order: List[str] = []
        waiters: List['asyncio.Task[bool]'] = []

        async def release_then_cancel_next() -> None:
            async with self._lock.turn('a'):
                entered.set()
                await release.wait()
            # Same step as the hand-off, so the granted waiter has not resumed yet.
            waiters[0].cancel()

        holder = asyncio.ensure_future(release_then_cancel_next())
        await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
        waiters.append(asyncio.ensure_future(self._record(order, 'granted')))
        waiters.append(asyncio.ensure_future(self._record(order, 'next')))
        await _let_pending_tasks_run()

        release.set()
        await asyncio.wait_for(asyncio.gather(holder, waiters[1]), WAIT_SECONDS)

        self.assertTrue(waiters[0].cancelled())
        self.assertEqual(['next'], order)
        self.assertEqual({}, self._lock._entries)

    async def test_exception_inside_a_turn_releases_it(self):
        order: List[str] = []

        with self.assertRaises(RuntimeError):
            async with self._lock.turn('a'):
                raise RuntimeError('actor method failed')

        await asyncio.wait_for(self._record(order, 'next'), WAIT_SECONDS)
        self.assertEqual(['next'], order)

    async def test_cancelled_turn_releases_it(self):
        holder, _ = await self._start_holding()
        order: List[str] = []
        waiter = asyncio.ensure_future(self._record(order, 'next'))
        await _let_pending_tasks_run()

        holder.cancel()

        await asyncio.wait_for(waiter, WAIT_SECONDS)
        self.assertTrue(holder.cancelled())
        self.assertEqual(['next'], order)

    async def test_reentrant_call_enters_once_reentrancy_is_allowed(self):
        entered = asyncio.Event()
        activated = asyncio.Event()
        release = asyncio.Event()

        async def root() -> None:
            async with self._lock.turn('a', 'chain') as turn:
                entered.set()
                await activated.wait()
                turn.allow_reentrancy()
                await release.wait()

        root_task = asyncio.ensure_future(root())
        await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
        order: List[str] = []
        reentrant = asyncio.ensure_future(self._record(order, 'reentrant', reentrancy_id='chain'))
        await _let_pending_tasks_run()

        self.assertEqual([], order)

        activated.set()
        reentered = await asyncio.wait_for(reentrant, WAIT_SECONDS)
        self.assertTrue(reentered)
        self.assertEqual(['reentrant'], order)
        self.assertFalse(root_task.done())
        release.set()
        await asyncio.wait_for(root_task, WAIT_SECONDS)
        self.assertEqual({}, self._lock._entries)

    async def test_reentrant_call_skips_queued_callers(self):
        holder, release = await self._start_holding(reentrancy_id='chain', allow_reentrancy=True)
        order: List[str] = []
        queued = asyncio.ensure_future(self._record(order, 'queued'))
        await _let_pending_tasks_run()

        reentered = await asyncio.wait_for(
            self._record(order, 'reentrant', reentrancy_id='chain'), WAIT_SECONDS
        )

        self.assertTrue(reentered)
        release.set()
        await asyncio.wait_for(asyncio.gather(holder, queued), WAIT_SECONDS)
        self.assertEqual(['reentrant', 'queued'], order)

    async def test_other_or_missing_reentrancy_ids_wait(self):
        for reentrancy_id in (None, '', 'other'):
            with self.subTest(reentrancy_id=reentrancy_id):
                holder, release = await self._start_holding(
                    reentrancy_id='chain', allow_reentrancy=True
                )
                order: List[str] = []
                waiter = asyncio.ensure_future(
                    self._record(order, 'waiter', reentrancy_id=reentrancy_id)
                )
                await _let_pending_tasks_run()

                self.assertEqual([], order)

                release.set()
                _, reentered = await asyncio.wait_for(asyncio.gather(holder, waiter), WAIT_SECONDS)
                self.assertFalse(reentered)
                self.assertEqual(['waiter'], order)

    async def test_is_in_chain(self):
        holder, release = await self._start_holding(reentrancy_id='chain')

        self.assertTrue(self._lock.is_in_chain('a', 'chain'))
        self.assertFalse(self._lock.is_in_chain('a', 'other'))
        self.assertFalse(self._lock.is_in_chain('a', None))
        self.assertFalse(self._lock.is_in_chain('b', 'chain'))

        release.set()
        await asyncio.wait_for(holder, WAIT_SECONDS)
        self.assertFalse(self._lock.is_in_chain('a', 'chain'))


class ActorTurnLockEventLoopTests(unittest.TestCase):
    """Manages its own event loops: IsolatedAsyncioTestCase runs in debug mode, which is too slow
    for 10,000 tasks."""

    def test_long_queue_runs_in_order(self):
        lock = ActorTurnLock()
        names = [str(index) for index in range(10_000)]
        order: List[str] = []

        async def scenario() -> None:
            entered = asyncio.Event()
            release = asyncio.Event()

            async def hold() -> None:
                async with lock.turn('a'):
                    entered.set()
                    await release.wait()

            async def record(name: str) -> None:
                async with lock.turn('a'):
                    order.append(name)

            holder = asyncio.ensure_future(hold())
            await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
            waiters = [asyncio.ensure_future(record(name)) for name in names]
            await _let_pending_tasks_run()

            release.set()
            await asyncio.wait_for(asyncio.gather(holder, *waiters), WAIT_SECONDS)

        asyncio.run(scenario())

        self.assertEqual(names, order)
        self.assertEqual({}, lock._entries)

    def test_waiter_whose_event_loop_closed_is_skipped(self):
        async def create_waiter() -> _Waiter:
            return _Waiter(None)

        closed_loop = asyncio.new_event_loop()
        orphan = closed_loop.run_until_complete(create_waiter())
        closed_loop.close()
        lock = ActorTurnLock()
        order: List[str] = []

        async def scenario() -> None:
            entered = asyncio.Event()
            release = asyncio.Event()

            async def hold() -> None:
                async with lock.turn('a'):
                    entered.set()
                    await release.wait()

            async def record(name: str) -> None:
                async with lock.turn('a'):
                    order.append(name)

            holder = asyncio.ensure_future(hold())
            await asyncio.wait_for(entered.wait(), WAIT_SECONDS)
            lock._entries['a'].waiters.append(orphan)
            waiter = asyncio.ensure_future(record('next'))
            await _let_pending_tasks_run()

            release.set()
            await asyncio.wait_for(asyncio.gather(holder, waiter), WAIT_SECONDS)

        asyncio.run(scenario())

        self.assertFalse(orphan.granted)
        self.assertEqual(['next'], order)
        self.assertEqual({}, lock._entries)

    def test_turns_from_threads_with_their_own_event_loops(self):
        lock = ActorTurnLock()
        counters_lock = threading.Lock()
        counters = {'inside': 0, 'max_inside': 0, 'completed': 0}
        errors: List[BaseException] = []

        async def take_turn() -> None:
            async with lock.turn('a'):
                with counters_lock:
                    counters['inside'] += 1
                    counters['max_inside'] = max(counters['max_inside'], counters['inside'])
                await asyncio.sleep(0.005)
                with counters_lock:
                    counters['inside'] -= 1
                    counters['completed'] += 1

        def take_turns() -> None:
            try:
                for _ in range(5):
                    asyncio.run(take_turn())
            except BaseException as exception:  # noqa: BLE001
                errors.append(exception)

        threads = [threading.Thread(target=take_turns) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(WAIT_SECONDS * 2)

        self.assertEqual([], [thread.name for thread in threads if thread.is_alive()])
        self.assertEqual([], errors)
        self.assertEqual(1, counters['max_inside'])
        self.assertEqual(20, counters['completed'])
        self.assertEqual({}, lock._entries)


if __name__ == '__main__':
    unittest.main()
