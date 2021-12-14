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

import uuid


class ActorId:
    """ActorId that represents the identity of an actor.

    Example::

        # create actorid with id 1
        actor_id = ActorId('1')

        # create random hex ActorId
        actor_random_id = ActorId.create_random_id()

    """

    def __init__(self, actor_id: str):
        if not isinstance(actor_id, str):
            raise TypeError(f"Argument actor_id must be of type str, not {type(actor_id)}")
        self._id = actor_id

    @classmethod
    def create_random_id(cls):
        """Creates new object of :class:`ActorId` with the random id value."""
        random_id = uuid.uuid1().hex
        return ActorId(random_id)

    @property
    def id(self) -> str:
        """Gets Actor ID string."""
        return self._id

    def __hash__(self):
        return hash(self._id)

    def __str__(self):
        return self._id

    def __eq__(self, other):
        if not other:
            return False
        return self._id == other.id

    def __ne__(self, other):
        if not other:
            return False

        return self._id != other.id
