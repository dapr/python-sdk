from dapr.actor import Actor
from dapr.actor.ext import actormethodname

class DemoActorInterface(object):
    @actormethodname("GetMyData")
    def get_my_data(self):
        pass

class DemoActor(Actor, DemoActorInterface):
    def __init__(self):
        super()
    
    def _on_activate(self):
        pass

    def _on_deactivate(self):
        pass

    def get_my_data(self):
        return "mydata"