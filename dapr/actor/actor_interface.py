# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from abc import ABC
from dapr.actor.runtime.methodcontext import ActorMethodContext

class ActorInterface(ABC):
    """A base class that Dapr Actor inherits.

    Actor requires to inherit ActorInterface as a base class.
    
    Example::

        class DaprActor(ActorInterface):
            def do_actor_method1(self, param):
                ...

            def do_actor_method2(self, param):
                ...
    """
    ...

def actormethod(name: str=None):
    """Decorate actor method to define the method invoked by the remote actor.
    
    This allows users to call the decorated name via the proxy client.

    Example::

        class DaprActor(ActorInterface):
            @actormethod(name='DoActorCall')
            def do_actor_call(self, param):
                ...

    """
    def wrapper(funcobj):
        funcobj.__actormethod__ = name
        funcobj.__isabstractmethod__ = True
        return funcobj
    return wrapper

def get_class_method_args(fn: type) -> list:
    args = fn.__code__.co_varnames[:fn.__code__.co_argcount]

    # Exclude self, cls arguments
    if args[0] == 'self' or args[0] == 'cls':
        args = args[1:]
    return list(args)

def get_method_arg_types(fn: type) -> list:
    annotations = getattr(fn, '__annotations__')
    args = get_class_method_args(fn)
    arg_types = []
    for arg_name in args:
        arg_type = object if arg_name not in annotations else annotations[arg_name]
        arg_types.append(arg_type)
    return arg_types

def get_method_return_types(fn: type) -> type:
    annotations = getattr(fn, '__annotations__')
    if not annotations['return']:
        return object
    else:
        return annotations['return']

def get_dispatchable_attrs(actor: object) -> dict:
    """Get the list of dispatchable attributes from actor.

    :param object actor: The actor object which inherits :class:`ActorInterface`
    :returns: The map from attribute to actor method
    :rtype: dict
    """
    # Find all user actor interfaces derived from ActorInterface
    actor_interfaces = []
    for cl in actor.mro():
        if issubclass(cl, ActorInterface):
            actor_interfaces.append(cl)
    
    if len(actor_interfaces):
        raise ValueError(f'{actor.__name__} has not inherited from ActorInterface')

    # Find all dispatchable attributes
    dispatch_map = {}
    for user_actor_cls in actor_interfaces:
        for attr, v in user_actor_cls.__dict__.items():
            if attr.startswith('_') or not callable(v):
                continue
            actor_method_name = getattr(v, '__actormethod__') if hasattr(v, '__actormethod__') else attr

            dispatch_map[actor_method_name] = {
                'method_name': attr,
                'arg_names': get_class_method_args(v),
                'arg_types': get_method_arg_types(v),
                'return_types': get_method_return_types(v)
            }

    return dispatch_map
