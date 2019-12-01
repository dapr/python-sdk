from enum import Enum
import asyncio

class StateChangeKind(Enum):
    """
    """

    NONE = 0
    ADD = 1
    UPDATE = 2
    REMOVE = 3


class StateMetadata(object):
    """
    """
    
    def __init__(self, value, value_type, change_kind):
        self.value = value
        self.type = value_type
        self.change_kind = change_kind
    
    @staticmethod
    def create(value, change_kind):
        return StateMetadata(value, type(value), change_kind)

    @staticmethod
    def create_for_remove():
        return StateMetadata(None, type(object), StateChangeKind.REMOVE)


class ActorStateManager(object):
    """
    """

    _actor_change_tracker = dict()

    def __init__(self, actor):
        self._actor = actor
        self._actor_type = actor.get_type()

    async def add_state(self, state_name, value):
        pass

    async def try_add_state(self, state_name, value):
        pass

    async def get_state(self, state_name, value):
        pass

    async def try_get_state(self, state_name, value):
        pass

    async def set_state(self, state_name, value):
        pass

    async def remove_state(self, state_name, value):
        pass

    async def try_remove_state(self, state_name, value):
        pass

    async def contains_state(self, state_name):
        pass

    async def get_or_add_state(self, state_name, value):
        pass

    async def get_or_update_state(self, state_name, add_value, update_value_factory_fn):
        pass

    async def get_state_name(self):
        pass

    async def clear_cache():
        pass

    async def save_state():
        pass

    async def is_state_marked_for_remove(self, state_name):
        pass

    async def try_get_state_from_state_provider(self, state_name):
        pass
