from abc import ABC, abstractmethod

class DaprClientBase(ABC):
    @abstractmethod
    def invoke_actor_method(self, actor_type, actor_id, method, data): pass