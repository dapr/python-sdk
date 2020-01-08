from abc import ABC, abstractmethod
from .statemanager import ActorStateManager

# http://code.activestate.com/recipes/285262-create-objects-from-variable-class-names/

class Actor(ABC):
    """
    Represents the base class for actors.
    The base type for actors, that provides the common functionality
    for actors that derive from Actor
    The state is preserved across actor garbage collections and fail-overs.
    """

    _dispatch_mapping = {}

    def __init__(self, actor_service, actor_id):
        self.id = actor_id
        self.actor_service = actor_service
        self._state_manager = ActorStateManager(self)
        self.is_dirty = False

    def on_activate_internal(self):
        pass

    def on_deactivate_internal(self):
        pass

    def on_pre_actor_method_internal(self, actor_method_context):
        pass

    def on_post_actor_method_internal(self, actor_method_context):
        pass

    def on_invoke_failed(self):
        self.is_dirty = True

    def reset_state(self):
        await self._state_manager.clear_cache()

    def fire_timer(self, timer_name):
        pass

    def _save_state(self):
        if not self.is_dirty:
            await self._state_manager.save_state()
    
    def _on_activate(self):
        pass

    def _on_deactivate(self):
        pass

    def _on_pre_actor_mehtod(self, actor_method_context):
        pass

    def _on_post_actor_method(self, actor_method_context):
        pass

    def _register_reminder(self, reminder_name, state, due_time, period):
        pass

    def _unregister_reminder(self, reminder):
        if isinstance(reminder, str):
            # reminder is str
            pass
        else:
            # reminder is IActorReminder
            pass

    def _register_timer(self, timer_cb, state, due_time, period):
        pass

    def _register_timer(self, timer_name, timer_cb, state, due_time, period):
        pass

    def _unregister_timer(self, timer):
        if isinstance(timer, str):
            # timer is str
            pass
        else:
            # timer is not str
            pass
