# -*- coding: utf-8 -*-
# Copyright 2021 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime

from dapr.actor import Actor, Remindable
from demo_actor_interface import DemoActorInterface
from typing import Optional


class DemoActor(Actor, DemoActorInterface, Remindable):
    """Implements DemoActor actor service

    This shows the usage of the below actor features:

    1. Actor method invocation
    2. Actor state store management
    3. Actor reminder
    4. Actor timer
    """

    def __init__(self, ctx, actor_id):
        super(DemoActor, self).__init__(ctx, actor_id)

    async def _on_activate(self) -> None:
        """An callback which will be called whenever actor is activated."""
        print(f'Activate {self.__class__.__name__} actor!', flush=True)

    async def _on_deactivate(self) -> None:
        """An callback which will be called whenever actor is deactivated."""
        print(f'Deactivate {self.__class__.__name__} actor!', flush=True)

    async def get_my_data(self) -> object:
        """An actor method which gets mydata state value."""
        has_value, val = await self._state_manager.try_get_state('mydata')
        print(f'has_value: {has_value}', flush=True)
        return val

    async def set_my_data(self, data) -> None:
        """An actor method which set mydata state value."""
        print(f'set_my_data: {data}', flush=True)
        data['ts'] = datetime.datetime.now(datetime.timezone.utc)
        await self._state_manager.set_state('mydata', data)
        await self._state_manager.save_state()

    async def clear_my_data(self) -> None:
        print('clear_my_data', flush=True)
        await self._state_manager.remove_state('mydata')
        await self._state_manager.save_state()

    async def set_reminder(self, enabled) -> None:
        """Enables and disables a reminder.

        Args:
            enabled (bool): the flag to enable and disable demo_reminder.
        """
        print(f'set reminder to {enabled}', flush=True)
        if enabled:
            # Register 'demo_reminder' reminder and call receive_reminder method
            await self.register_reminder(
                'demo_reminder',  # reminder name
                b'reminder_state',  # user_state (bytes)
                # The amount of time to delay before firing the reminder
                datetime.timedelta(seconds=5),
                datetime.timedelta(seconds=5),  # The time interval between firing of reminders
                datetime.timedelta(seconds=5),
            )
        else:
            # Unregister 'demo_reminder'
            await self.unregister_reminder('demo_reminder')
        print('set reminder is done', flush=True)

    async def set_timer(self, enabled) -> None:
        """Enables and disables a timer.

        Args:
            enabled (bool): the flag to enable and disable demo_timer.
        """
        print(f'set_timer to {enabled}', flush=True)
        if enabled:
            # Register 'demo_timer' timer and call timer_callback method
            await self.register_timer(
                'demo_timer',  # timer name
                self.timer_callback,  # Callback method
                'timer_state',  # Parameter to pass to the callback method
                # Amount of time to delay before the callback is invoked
                datetime.timedelta(seconds=5),
                datetime.timedelta(seconds=5),  # Time interval between invocations
                datetime.timedelta(seconds=5),
            )
        else:
            # Unregister 'demo_timer'
            await self.unregister_timer('demo_timer')
        print('set_timer is done', flush=True)

    async def timer_callback(self, state) -> None:
        """A callback which will be called whenever timer is triggered.

        Args:
            state (object): an object which is defined when timer is registered.
        """
        print(f'time_callback is called - {state}', flush=True)

    async def receive_reminder(
        self,
        name: str,
        state: bytes,
        due_time: datetime.timedelta,
        period: datetime.timedelta,
        ttl: Optional[datetime.timedelta] = None,
    ) -> None:
        """A callback which will be called when reminder is triggered."""
        print(f'receive_reminder is called - {name} reminder - {str(state)}', flush=True)

    async def get_reentrancy_status(self) -> bool:
        """For Testing Only: An actor method which gets reentrancy status."""
        from dapr.actor.runtime.reentrancy_context import reentrancy_ctx

        return reentrancy_ctx.get(None) is not None
