
class ActorTypeInformation(object):
    """
    """

    def __init__(self, actor):
        self._implType = actor
    
    def is_remindable(self):
        return False
    
    @property
    def name(self):
        return self._implType.__name__

    @property
    def implementation_type(self):
        return self._implType
