import threading
import json

class ActorManager(object):
    """
    Manage Actors of a specific actor type.
    """

    def __init__(self, actor_service):
        self._actor_service = actor_service
        self._active_actors = {}
        self._active_actors_lock = threading.RLock()

    def dispatch(self, actor_id, actor_method_name, body):
        if len(body) == 0:
            return self._active_actors[actor_id].dispatch_method(actor_method_name)
        else:
            # TODO: Add deserialization
            obj = json.load(body)
            return self._active_actors[actor_id].dispatch_method(actor_method_name, obj)

    def fire_reminder(self, actor_id, reminder_name, body):
        pass

    def fire_timer(self, actor_id, timer_name):
        pass

    def activate_actor(self, actor_id):
        actor = self._actor_service.create_actor(actor_id)
        actor.on_activate_internal()

        with self._active_actors_lock:
            self._active_actors[actor_id] = actor

    def deactivate_actor(self, actor_id):
        with self._active_actors_lock:
            self._active_actors.pop(actor_id, None)
