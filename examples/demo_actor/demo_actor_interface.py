from dapr.actor.actor_interface import ActorInterface, actormethodname

class DemoActorInterface(ActorInterface):
    @actormethodname(name="GetMyData")
    def get_my_data(self) -> object:
        ...
    
    @actormethodname(name="SetMyData")
    def set_my_data(self, data: object) -> None:
        ...
