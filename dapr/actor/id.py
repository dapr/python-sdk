# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
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
