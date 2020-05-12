# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import datetime

from dapr.actor import Actor, Remindable
from examples.demo_actor.demo_actor_interface import DemoActorInterface


class DemoActor(Actor, DemoActorInterface, Remindable):
    """Implements DemoActor actor service
    
    This shows the usage of the below actor features:

    1. Actor method invocation
    2. Actor State store management
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

    async def set_reminder(self, enabled) -> None:
        """An actor method which enables and disables a reminder.

        :param bool enabled: the flag to enable and disable demo_reminder
        """
        print(f'set reminder to {enabled}', flush=True)
        if enabled:
            # Register 'demo_reminder' reminder and call receive_reminder method
            await self.register_reminder(
                'demo_reminder', b'reminder_state', 
                datetime.timedelta(seconds=5), datetime.timedelta(seconds=5))
        else:
            # Unregister 'demo_reminder'
            await self.unregister_reminder('demo_reminder')
        print(f'set reminder is done', flush=True)

    async def set_timer(self, enabled) -> None:
        """An actor method which enables and disables a timer.

        :param bool enabled: the flag to enable and disable demo_timer
        """
        print(f'set_timer to {enabled}', flush=True)
        if enabled:
            # Register 'demo_timer' timer and call timer_callback method
            await self.register_timer(
                'demo_timer', 
                self.timer_callback,
                'timer_state', 
                datetime.timedelta(seconds=5),
                datetime.timedelta(seconds=5))
        else:
            # Unregister 'demo_timer'
            await self.unregister_timer('demo_timer')
        print(f'set_timer is done', flush=True)
    
    async def timer_callback(self, state) -> None:
        """A callback which will be called whenever timer is triggered.

        :param object state: an object which is defined when timer is registered.
        """
        print(f'time_callback is called - {state}', flush=True)

    async def receive_reminder(self, name: str, state: bytes,
                               due_time: datetime.timedelta, period: datetime.timedelta) -> None:
        """A callback which will be called when reminder is triggered.

        :param str name: the name of the reminder to register. the name must be unique per actor.
        :param bytes state: the user state passed to the reminder invocation.
        :param datetime.timedelta due_time: the amount of time to delay before invoking the reminder for the first time.
        :param datetime.timedelta period: the time interval between reminder invocations after the first invocation.
        """
        print(f'receive_reminder is called - {name} reminder - {state}', flush=True)

