import asyncio

class ActorStateManager(object):
    """
    """

    _state_change_tracker = {}

    def __init__(self, actor):
        self._actor = actor

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

    async def clear_cache(self):
        pass

    async def save_state(self):
        pass

    async def is_state_marked_for_remove(self, state_name):
        pass

    async def try_get_state_from_state_provider(self, state_name):
        pass
