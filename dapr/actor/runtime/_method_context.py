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

from dapr.actor.runtime._call_type import ActorCallType


class ActorMethodContext:
    """A Actor method context that contains method information invoked
    by :class:`ActorRuntime`.
    """

    def __init__(self, method_name: str, call_type: ActorCallType):
        self._method_name = method_name
        self._calltype = call_type

    @property
    def method_name(self) -> str:
        """Gets the method name."""
        return self._method_name

    @property
    def call_type(self) -> ActorCallType:
        """Gets :class:`ActorCallType` for this method."""
        return self._calltype

    @classmethod
    def create_for_actor(cls, method_name: str):
        """Creates :class:`ActorMethodContext` object for actor method."""
        return ActorMethodContext(method_name, ActorCallType.actor_interface_method)

    @classmethod
    def create_for_timer(cls, method_name: str):
        """Creates :class:`ActorMethodContext` object for timer_method."""
        return ActorMethodContext(method_name, ActorCallType.timer_method)

    @classmethod
    def create_for_reminder(cls, method_name: str):
        """Creates :class:`ActorMethodContext` object for reminder_method."""
        return ActorMethodContext(method_name, ActorCallType.reminder_method)
