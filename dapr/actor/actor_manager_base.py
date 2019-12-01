from abc import ABC

class ActorManagerBase(ABC):
    def __init__(self, actor_service):
        self._actor_service = actor_service
