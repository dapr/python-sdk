from actors.runtime.actor_state_manager import ActorStateManager
from abc import ABC, abstractmethod
import asyncio

class Actor(ABC):
    """Represents the base class for actors.
    The base type for actors, that provides the common functionality
    for actors that derive from Actor
    The state is preserved across actor garbage collections and fail-overs.
    """
    def __init__(self, actor_service, actor_id):
        self.id = actor_id
        self.actor_service = actor_service
        self._state_manager = ActorStateManager(self)
        self.is_dirty = false

    async def on_activate_internal(self):
        pass

    async def on_deactivate_internal(self):
        pass

    async def on_pre_actor_method_internal(self, actor_method_context):
        pass

    async def on_post_actor_method_internal(self, actor_method_context):
        pass

    def on_invoke_failed(self):
        self.is_dirty = true

    async def reset_state(self):
        await self._state_manager.clear_cache()

    async def fire_timer(timer_name):
        pass

    async def _save_state(self):
        if not self.is_dirty:
            await self.state_manager.save_state()
    
    @abstractmethod
    async def _on_activate():
        ...

    @abstractmethod
    async def _on_deactivate():
        ...

    @abstractmethod
    async def _on_pre_actor_mehtod(actor_method_context):
        ...

    @abstractmethod
    async def _on_post_actor_method(actor_method_context):
        ...

    async def _register_reminder(reminder_name, state, due_time, period):
        pass

    async def _unregister_reminder(reminder):
        if isinstance(reminder, str):
            # reminder is str
            pass
        else:
            # reminder is IActorReminder
            pass

    async def _register_timer(timer_cb, state, due_time, period):
        pass

    async def _register_timer(timer_name, timer_cb, state, due_time, period):
        pass

    async def _unregister_timer(timer):
        if isinstance(timer, str):
            # timer is str
            pass
        else:
            # timer is not str
            pass
