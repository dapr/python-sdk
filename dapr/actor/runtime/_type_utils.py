# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Any, Dict, List, Type

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.runtime.actor import Actor


def get_class_method_args(func: Any) -> List[str]:
    args = func.__code__.co_varnames[:func.__code__.co_argcount]

    # Exclude self, cls arguments
    if args[0] == 'self' or args[0] == 'cls':
        args = args[1:]
    return list(args)


def get_method_arg_types(func: Any) -> List[Type]:
    annotations = getattr(func, '__annotations__')
    args = get_class_method_args(func)
    arg_types = []
    for arg_name in args:
        arg_type = object if arg_name not in annotations else annotations[arg_name]
        arg_types.append(arg_type)
    return arg_types


def get_method_return_types(func: Any) -> Type:
    annotations = getattr(func, '__annotations__')
    if len(annotations) == 0 or not annotations['return']:
        return object
    return annotations['return']


def get_dispatchable_attrs_from_interface(
        actor_interface: Type[ActorInterface],
        dispatch_map: Dict[str, Any]) -> None:
    for attr, v in actor_interface.__dict__.items():
        if attr.startswith('_') or not callable(v):
            continue
        actor_method_name = getattr(v, '__actormethod__') if hasattr(v, '__actormethod__') else attr

        dispatch_map[actor_method_name] = {
            'actor_method': actor_method_name,
            'method_name': attr,
            'arg_names': get_class_method_args(v),
            'arg_types': get_method_arg_types(v),
            'return_types': get_method_return_types(v)
        }


def get_dispatchable_attrs(actor_class: Type[Actor]) -> Dict[str, Any]:
    """Gets the list of dispatchable attributes from actor.

    Args:
        actor_class (type): The actor object which inherits :class:`ActorInterface`

    Returns:
        Dict[str, Any]: The map from attribute to actor method.

    Raises:
        ValueError: `actor_class` doesn't inherit :class:`ActorInterface`.
    """
    # Find all user actor interfaces derived from ActorInterface
    actor_interfaces = get_actor_interfaces(actor_class)
    if len(actor_interfaces) == 0:
        raise ValueError(f'{actor_class.__name__} has not inherited from ActorInterface')

    # Find all dispatchable attributes
    dispatch_map: Dict[str, Any] = {}
    for user_actor_cls in actor_interfaces:
        get_dispatchable_attrs_from_interface(user_actor_cls, dispatch_map)

    return dispatch_map


def is_dapr_actor(cls: Type[Actor]) -> bool:
    """Checks if class inherits :class:`Actor`.

    Args:
        cls (type): The Actor implementation.

    Returns:
        bool: True if cls inherits :class:`Actor`. Otherwise, False
    """
    return issubclass(cls, Actor)


def get_actor_interfaces(cls: Type[Actor]) -> List[Type[ActorInterface]]:
    """Gets the list of the base classes that inherits :class:`ActorInterface`.

    Args:
        cls (:class:`Actor`): The Actor object that inherit :class:`Actor` and
            :class:`ActorInterfaces`.

    Returns:
        List: the list of classes that inherit :class:`ActorInterface`.
    """
    actor_bases = []
    for cl in cls.mro():
        if ActorInterface in cl.__bases__:
            actor_bases.append(cl)

    return actor_bases
