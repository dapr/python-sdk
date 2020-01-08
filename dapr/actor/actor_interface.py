from abc import ABC

class ActorInterface(ABC):
    pass

def actormethodname(name = None):

    def methodname(funcobj):
        funcobj.__methodname__ = funcobj.__name__ if name is None else name
        funcobj.__isabstractmethod__ = True
        return funcobj
    return methodname