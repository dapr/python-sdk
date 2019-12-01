
class ActorService(object):
    
    def __init__(self, actor_type_info, actor_factory):
        self.actor_type_info = actor_type_info
        self.actor_factory = actor_factory
        # self.state_provider = ACtorStateProvider(xxx)

    def create_actor(self, actor_id):
        return self.actor_factory.invoke(self, actor_id)
    
    def _default_actor_factory(actor_service, actor_id):
        pass