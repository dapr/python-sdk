import threading
from .service import ActorService
from .typeinformation import ActorTypeInformation
from .manager import ActorManager
from .id import ActorId

class ActorRuntime(object):
    """
    Register the types allows the runtime to create instances of the actor.

    Contains methods to register actor types.
    """

    _actor_managers = {}
    _actor_managers_lock = threading.RLock()

    @classmethod
    def register_actor(cls, actor, actor_service_factory = None):
        """
        Register an :class:`Actor` with the runtime.
        """

        actor_type_info = ActorTypeInformation(actor)

        actor_service = None
        if actor_service_factory is not None:
            actor_service = actor_service_factory.invoke(actor_type_info)
        else:
            actor_service = ActorService(actor_type_info)

        # Create an ActorManager, override existing entry if registered again.
        cls._actor_managers[actor_type_info.name] = ActorManager(actor_service)
    
    @classmethod
    def get_registered_actor_types(cls):
        return [actor_type for actor_type in cls._actor_managers.keys()]

    @classmethod
    def activate(cls, actor_type_name, actor_id):
        """
        Activate an actor for an actor type with given actor id.
        """
        
        cls.get_actor_manager(actor_type_name).activate_actor(ActorId(actor_id))

    @classmethod
    def deactivate(cls, actor_type_name, actor_id):
        """
        Deactivates an actor for an actor type with given actor id
        """

        cls.get_actor_manager(actor_type_name).deactivate_actor(ActorId(actor_id))

    @classmethod
    def fire_reminder(cls, actor_type_name, actor_id, reminder_name, request_body):
        """
        Fires a reminder for the Actor
        """

        cls.get_actor_manager(actor_type_name).fire_reminder(ActorId(actor_id), actor_id, reminder_name, request_body)

    @classmethod
    def fire_timer(cls, actor_type_name, actor_id, timer_name):
        """
        Fires a reminder for the Actor
        """

        cls.get_actor_manager(actor_type_name).fire_timer(ActorId(actor_id), actor_id, timer_name)

    @classmethod
    def dispatch(cls, actor_type_name, actor_id, actor_method_name, request_body):
        
        return cls.get_actor_manager(actor_type_name).dispatch(ActorId(actor_id), actor_method_name, request_body)

    @classmethod
    def get_actor_manager(cls, actor_type_name):
        with cls._actor_managers_lock:
            return cls._actor_managers.get(actor_type_name)

