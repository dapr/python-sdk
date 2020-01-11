from .methodcontext import ActorMethodContext
from dapr.clients import DaprHttpClient

class ActorProxyFactory(object):
    """
    Represents a factory class to create a proxy to the remote actor objects
    """

    def __init__(self):
        # TODO: HTTP client
        self._dapr_client = DaprHttpClient()

    def create(self, actor_interface, actor_type, actor_id):
        actor_proxy = ActorProxy()
        actor_proxy.initialize(self._dapr_client, actor_interface, actor_type, actor_id)

        return actor_proxy

class ActorProxy(object):
    """
    Provides the base implementation for the proxy to the remote actor objects
    The proxy object can be used used for client-to-actor and actor-to-actor communication.
    """

    _default_proxy_factory = ActorProxyFactory()

    def __init__(self):
        self._actor_id = None
        self._actor_type = ""
        self._dispatchable_attr = {}
        self._callable_proxies = {}

    @property
    def actor_id(self):
        return self._actor_id
    
    @property
    def actor_type(self):
        return self._actor_type

    def initialize(self, client, actor_interface, actor_type, actor_id):
        self._dapr_client = client
        self._actor_id = actor_id
        self._actor_type = actor_type
        self._actor_interface = actor_interface
    
    @classmethod
    def create(cls, actor_interface, actor_type, actor_id):
        return cls._default_proxy_factory.create(actor_interface, actor_type, actor_id)

    def _build_dispatchable_attrs(self):
        dispatch_map = {}
        for attr, v in self._actor_interface.__dict__.items():
            if attr.startswith('_') or not callable(v):
                continue

            actor_method_name = getattr(v, '__actormethod__') if hasattr(v, '__actormethod__') else attr
            dispatch_map[actor_method_name] = ActorMethodContext.create_for_actor(actor_method_name)

        return dispatch_map

    def __getattr__(self, name):
        if name not in self._dispatchable_attr:
            self._dispatchable_attr = self._build_dispatchable_attrs()
        
        attr_calltype = self._dispatchable_attr.get(name)
        if attr_calltype is None:
            raise AttributeError('{} has no attribute {!r}'.format(self._actor_interface.__class__, name))

        if name not in self._callable_proxies:
            self._callable_proxies[name] = CallableProxies(
                self._dapr_client,
                self._actor_type,
                self._actor_id,
                name)
        
        return self._callable_proxies[name]

class CallableProxies(object):
    def __init__(self, dapr_client, actor_type, actor_id, method):
        self._dapr_client = dapr_client
        self._actor_type = actor_type
        self._actor_id = actor_id
        self._method = method
    
    def __call__(self, *args, **kwargs):
        obj = None if len(args) == 0 else args[0]

        return self._dapr_client.invoke_actor_method(
            self._actor_type,
            str(self._actor_id),
            self._method,
            obj)