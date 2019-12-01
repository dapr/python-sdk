from enum import Enum

class ActorCallType(Enum):
    """Represents the call-type associated with the method invoked by actor runtime.
    This is provided as part of ActorMethodContext which is passed as argument to
    Actor._on_pre_actor_method and Actor._on_post_actor_method
    """
    ACTOR_INTERFACE_METHOD = 0
    TIMER_METHOD = 1
    REMINDER_METHOD = 2


class ActorMethodContext(object):
    """Contains information about the method that is invoked by actor runtime
    """
    def __init__(self, method_name, call_type):
        self._method_name = method_name
        self._call_type = call_type

    @property
    def method_name(self):
        return self._method_name

    @property
    def call_type(self):
        return self._call_type

    @staticmethod
    def create_for_actor(method_name):
        return ActorMethodContext(method_name, ActorCallType.ACTOR_INTERFACE_METHOD)
    
    @staticmethod
    def create_for_timer(method_name):
        return ActorMethodContext(method_name, ActorCallType.TIMER_METHOD)

    @staticmethod
    def create_for_reminder(method_name):
        return ActorMethodContext(method_name, ActorCallType.REMINDER_METHOD)
