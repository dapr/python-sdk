from .id import ActorId

class ActorReminder(object):
    """
    """

    def __init__(self, actor_id, reminder_name, reminder_info):
        self._name = reminder_name
        self._owner_actor_id = actor_id
        self._reminder_info = reminder_info

    @property
    def actor_id(self) -> ActorId:
        return self._owner_actor_id
    
    def state(self) -> bytearray:
        return self._reminder_info.data