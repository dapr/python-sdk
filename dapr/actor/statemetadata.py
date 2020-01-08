from enum import Enum

class StateChangeKind(Enum):
    """
    Represents the kind of state change for an actor state when saves change is called to a set of actor states.
    """

    # No change in state.
    NONE = 0
    # The state needs to be added.
    ADD = 1
    # The state needs to be updated.
    UPDATE = 2
    # The state needs to be removed.
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

