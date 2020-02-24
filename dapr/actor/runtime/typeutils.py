# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.runtime.actor import Actor

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

def is_dapr_actor(cls: object) -> bool:
    """Check if class inherits :class:`Actor`.

    :param object cls: The Actor implementation
    :returns: True if cls inherits :class:`Actor`. Otherwise, False
    :rtype: bool
    """
    return issubclass(cls.__class__, Actor)

def get_non_actor_parent_type(cls: object) -> object:
    """Get non-actor parent type by traversing parent type node

    :param object cls: The actor object
    :returns: The non actor parent object
    :rtype: object
    """
    bases = cls.__bases__[:]

    # Remove Actor and ActorInterface bases before traverse
    found_actor_interface = False
    for cl_i in range(len(bases)):
        if bases[cl_i] is Actor:
            del bases[cl_i]
        if bases[cl_i] is ActorInterface:
            del bases[cl_i]
            found_actor_interface = True

    # cls is non actor parent node if cls does not inherit ActorInterface
    if not found_actor_interface: return cls

    # Traverse non-ActorInterface base types except for ActorInterface
    for cl in bases:
        non_actor_parent = get_non_actor_parent_type(cl)
        if non_actor_parent is not None:
            return non_actor_parent

    return None

def get_actor_interfaces(cls) -> list:
    """Get the list of the base classes that inherit :class:`ActorInterface`.
    
    :param object cls: The Actor object that inherit :class:`Actor` and
                       :class:`ActorInterfaces`
    :returns: the list of classes that inherit :class:`ActorInterface`
    :rtype: list
    """
    actor_bases = []
    for cl in cls.__bases__:
        if issubclass(cl, ActorInterface):
            if get_non_actor_parent_type(cl) is not None:
                continue
            actor_bases.append(cl)

    return actor_bases
