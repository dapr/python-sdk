from enum import Enum

class ActorCallType(Enum):
    """
    Represents the call-type associated with the method invoked by actor runtime.
    This is provided as part of ActorMethodContext which is passed as argument to
    Actor._on_pre_actor_method and Actor._on_post_actor_method
    """
    # Specifies that the method invoked is an actor interface method for a given client request.
    actor_interface_method = 0
    # Specifies that the method invoked is a timer callback method.
    timer_method = 1
    # Specifies that the method is when a reminder fires.
    reminder_method = 2
