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

from dapr.actor.actor_interface import ActorInterface, actormethod
from dapr.actor.client.proxy import ActorProxy, ActorProxyFactory
from dapr.actor.id import ActorId
from dapr.actor.runtime.actor import Actor
from dapr.actor.runtime.remindable import Remindable
from dapr.actor.runtime.runtime import ActorRuntime


__all__ = [
    'ActorInterface',
    'ActorProxy',
    'ActorProxyFactory',
    'ActorId',
    'Actor',
    'ActorRuntime',
    'Remindable',
    'actormethod',
]
