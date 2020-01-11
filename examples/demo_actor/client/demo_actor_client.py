from dapr.actor import ActorProxy, ActorId
from examples.demo_actor.demo_actor_interface import DemoActorInterface

proxy = ActorProxy.create(DemoActorInterface, 'DemoActor', ActorId('1'))
my_data = proxy.GetMyData()

print(my_data)