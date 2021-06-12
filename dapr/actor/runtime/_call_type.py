# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
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
