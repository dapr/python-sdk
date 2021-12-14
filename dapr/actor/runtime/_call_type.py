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

from enum import Enum


class ActorCallType(Enum):
    """A enumeration that represents the call-type associated with the actor method.
    :class:`ActorMethodContext` includes :class:`ActorCallType` passing to
    :meth:`Actor._on_pre_actor_method` and :meth:`Actor._on_post_actor_method`
    """
    # Specifies that the method invoked is an actor interface method for a given client request.
    actor_interface_method = 0
    # Specifies that the method invoked is a timer callback method.
    timer_method = 1
    # Specifies that the method is when a reminder fires.
    reminder_method = 2
