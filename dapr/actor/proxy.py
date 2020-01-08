
class ActorProxyFactory(object):
    """
    Represents a factory class to create a proxy to the remote actor objects
    """

    def __init__(self):
        # TODO: HTTP client
        self._dapr_interactor = None

    def create(self, actor_id, actor_type):
        actor_proxy = ActorProxy()

        # TODO: pass remoting client
        actor_proxy.initialize(None, actor_id, actor_type)

        return actor_proxy

class ActorProxy(object):
    """
    Provides the base implementation for the proxy to the remote actor objects
    The proxy object can be used used for client-to-actor and actor-to-actor communication.
    """
    def __init__(self):
        self._actor_id = None
        self._actor_type = ""

    @property
    def actor_id(self):
        return self._actor_id
    
    @property
    def actor_type(self):
        return self._actor_type

    def initialize(self, client, actor_id, actor_type):
        self._dapr_client = client
        self._actor_id = actor_id
        self._actor_type = actor_type
