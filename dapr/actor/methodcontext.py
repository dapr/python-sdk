from .calltype import ActorCallType

class ActorMethodContext(object):
    """
    Contains information about the method that is invoked by actor runtime
    """
    
    _call_type: ActorCallType

    def __init__(self, method_name, call_type):
        self._method_name = method_name
        self._call_type = call_type

    @property
    def method_name(self):
        return self._method_name

    @property
    def call_type(self):
        return self._call_type

    @classmethod
    def create_for_actor(cls, method_name):
        return ActorMethodContext(method_name, ActorCallType.ACTOR_INTERFACE_METHOD)
    
    @classmethod
    def create_for_timer(cls, method_name):
        return ActorMethodContext(method_name, ActorCallType.TIMER_METHOD)

    @classmethod
    def create_for_reminder(cls, method_name):
        return ActorMethodContext(method_name, ActorCallType.REMINDER_METHOD)
