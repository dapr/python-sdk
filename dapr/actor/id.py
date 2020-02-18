# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import secrets
import threading

class ActorId:
    """ActorId that represents the identity of an actor within :class:`ActorService`.
    """
    _rand_id_lock = threading.Lock()

    def __init__(self, id):
        if not isinstance(id, str):
            raise TypeError(f"Argument id must be of type str, not {type(id)}")
        self._id = id
    
    def create_random_id(self):
        """Creates new object of :class:`ActorId` with the random id value
        This is a thread-safe operation that generates new random :class:`ActorId`
        :rtype: :class:`ActorId` object
        """
        random_id = ""

        with self._rand_id_lock:
            random_id = secrets.token_hex(8)

        return ActorId(random_id)
    
    @property
    def id(self):
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
