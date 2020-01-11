from abc import ABC
import functools

class ActorInterface(ABC): ...

def actormethod(name = None):
    def wrapper(funcobj):
        funcobj.__actormethod__ = name
        return funcobj
    return wrapper