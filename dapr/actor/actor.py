# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .actor_interface import ActorInterface

# http://code.activestate.com/recipes/285262-create-objects-from-variable-class-names/

class Actor(object):
    """
    Represents the base class for actors.
    The base type for actors, that provides the common functionality
    for actors that derive from Actor
    The state is preserved across actor garbage collections and fail-overs.
    """

    def __init__(self, actor_service, actor_id):
        self.id = actor_id
        self.actor_service = actor_service
        self._dispatch_mapping = {}

    def on_activate_internal(self):
        self._on_activate()

    def on_deactivate_internal(self):
        self._on_deactivate()

    def on_pre_actor_method_internal(self, actor_method_context):
        pass

    def on_post_actor_method_internal(self, actor_method_context):
        pass

    def dispatch_method(self, name, *args, **kwargs):
        if name not in self._dispatch_mapping:
            if not issubclass(self.__class__, ActorInterface):
                raise AttributeError('{} does not implement ActorInterface'.format(self.__class__))

            self._dispatch_mapping = getattr(self.__class__, 'get_dispatchable_attrs')()

            if name not in self._dispatch_mapping:
                raise AttributeError(
                    'type object {!r} has no method {!r}'.format(
                        self.__class__.__name__, name
                    )
                )

        return getattr(self, self._dispatch_mapping[name].method_name)(*args, **kwargs)

    def _on_activate(self): pass

    def _on_deactivate(self): pass

    def _on_pre_actor_method(self, actor_method_context): pass

    def _on_post_actor_method(self, actor_method_context): pass
