from dapr.actor import Actor
from examples.demo_actor.demo_actor_interface import DemoActorInterface

class DemoActor(Actor, DemoActorInterface):
    def __init__(self, actor_service, actor_id):
        super(Actor, actor_service, actor_id)

        # Set default data
        self._mydata = {
            "data": "default"
        }
    
    def _on_activate(self):
        pass

    def _on_deactivate(self):
        pass

    def get_my_data(self) -> object:
        return self._mydata
    
    def set_my_data(self, data) -> None:
        self._mydata = data
