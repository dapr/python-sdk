# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import threading
import uuid

class ActorId:
    """ActorId that represents the identity of an actor.

    Example::

        # create actorid with id 1
        actor_id = ActorId('1')

        # create 8-digit random hex ActorId
        actor_random_id = ActorId.create_random_id()

    """

    def __init__(self, id: str):
        if not isinstance(id, str):
            raise TypeError(f"Argument id must be of type str, not {type(id)}")
        self._id = id
    
    @classmethod
    def create_random_id(cls):
        """Creates new object of :class:`ActorId` with the random id value

        This is a thread-safe operation that generates new random :class:`ActorId`

        :returns: ActorId with random id
        :rtype: :class:`ActorId`
        """
        random_id = uuid.uuid1().hex
        return ActorId(random_id)
    
    @property
    def id(self) -> str:
        return self._id
    
    def __hash__(self):
        return hash(self._id)
    
    def __str__(self):
        return f'{self._id}'
    
    def __eq__(self, other):
        if not other:
            return False        
        return self._id == other.id

    def __ne__(self, other):
        if not other:
            return False

        return self._id != other.id
