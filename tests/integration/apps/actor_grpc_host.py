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

Actor host over the gRPC actor stream for integration tests.

Registers GrpcIntegrationActor with ActorGrpcHost and serves callbacks over
the SubscribeActorEventsAlpha1 stream. ActorGrpcHost owns the minimal
app-channel listener daprd requires (on APP_PORT), so this app writes no
server boilerplate.
"""

import asyncio
from datetime import timedelta
from typing import Dict, Optional

from dapr.actor import Actor, ActorGrpcHost, ActorInterface, Remindable, actormethod
from dapr.actor.runtime.config import ActorRuntimeConfig, ActorTypeConfig
from dapr.actor.runtime.runtime import ActorRuntime

HOLD_TURN_SECONDS = 1.0

# Per actor ID, outside the actor so a reactivation cannot reset them.
_turns: Dict[str, Dict[str, int]] = {}


class GrpcIntegrationActorInterface(ActorInterface):
    @actormethod(name='GetActivationCount')
    async def get_activation_count(self) -> int: ...

    @actormethod(name='SetData')
    async def set_data(self, data: object) -> None: ...

    @actormethod(name='GetData')
    async def get_data(self) -> object: ...

    @actormethod(name='StartReminder')
    async def start_reminder(self) -> None: ...

    @actormethod(name='StopReminder')
    async def stop_reminder(self) -> None: ...

    @actormethod(name='GetReminderEvidence')
    async def get_reminder_evidence(self) -> object: ...

    @actormethod(name='StartTimer')
    async def start_timer(self) -> None: ...

    @actormethod(name='StopTimer')
    async def stop_timer(self) -> None: ...

    @actormethod(name='GetTimerEvidence')
    async def get_timer_evidence(self) -> object: ...


class GrpcIntegrationActor(Actor, GrpcIntegrationActorInterface, Remindable):
    async def _on_activate(self) -> None:
        _, count = await self._state_manager.try_get_state('activations')
        await self._state_manager.set_state('activations', (count or 0) + 1)
        await self._state_manager.save_state()

    async def get_activation_count(self) -> int:
        _, count = await self._state_manager.try_get_state('activations')
        return count or 0

    async def set_data(self, data: object) -> None:
        await self._state_manager.set_state('data', data)
        await self._state_manager.save_state()

    async def get_data(self) -> object:
        _, data = await self._state_manager.try_get_state('data')
        return data

    async def start_reminder(self) -> None:
        await self.register_reminder(
            'itest_reminder', b'rstate', timedelta(seconds=1), timedelta(seconds=5)
        )

    async def stop_reminder(self) -> None:
        await self.unregister_reminder('itest_reminder')

    async def get_reminder_evidence(self) -> object:
        _, evidence = await self._state_manager.try_get_state('reminder_evidence')
        return evidence

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: timedelta,
        period: timedelta,
        ttl: Optional[timedelta] = None,
    ) -> None:
        await self._state_manager.set_state('reminder_evidence', state.decode('utf-8'))
        await self._state_manager.save_state()

    async def start_timer(self) -> None:
        await self.register_timer(
            'itest_timer',
            self.timer_callback,
            {'n': 7},
            timedelta(seconds=1),
            timedelta(seconds=5),
        )

    async def stop_timer(self) -> None:
        await self.unregister_timer('itest_timer')

    async def get_timer_evidence(self) -> object:
        _, evidence = await self._state_manager.try_get_state('timer_evidence')
        return evidence

    async def timer_callback(self, state) -> None:
        await self._state_manager.set_state('timer_evidence', state)
        await self._state_manager.save_state()


class TurnHoldingActorInterface(ActorInterface):
    @actormethod(name='HoldTurn')
    async def hold_turn(self) -> None: ...

    @actormethod(name='GetTurns')
    async def get_turns(self) -> object: ...


class TurnHoldingActor(Actor, TurnHoldingActorInterface):
    """Counts how many HoldTurn calls run at once on each actor ID."""

    async def hold_turn(self) -> None:
        turns = self._turns()
        turns['started'] += 1
        turns['running'] += 1
        turns['max_running'] = max(turns['max_running'], turns['running'])
        try:
            await asyncio.sleep(HOLD_TURN_SECONDS)
        finally:
            turns['running'] -= 1
        turns['completed'] += 1

    async def get_turns(self) -> object:
        return dict(self._turns())

    def _turns(self) -> Dict[str, int]:
        initial = {'started': 0, 'running': 0, 'max_running': 0, 'completed': 0}
        return _turns.setdefault(self.id.id, initial)


async def main() -> None:
    # Short idle timeout so the idle-deactivation test completes quickly. TurnHoldingActor keeps
    # a longer one: calls abandoned by their callers leave it idle in daprd's eyes, and an idle
    # deactivation would cancel the call that reads the counters.
    turn_holding_config = ActorTypeConfig(
        TurnHoldingActor.__name__, actor_idle_timeout=timedelta(minutes=5)
    )
    ActorRuntime.set_actor_config(
        ActorRuntimeConfig(
            actor_idle_timeout=timedelta(seconds=3), actor_type_configs=[turn_holding_config]
        )
    )

    host = ActorGrpcHost()
    await host.register_actor(GrpcIntegrationActor)
    await host.register_actor(TurnHoldingActor)
    print('GrpcIntegrationActor host started', flush=True)
    await host.run_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
