# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.runtime.methodcontext import ActorMethodContext
from dapr.actor.runtime.context import ActorRuntimeContext

class Actor:
    """A base class of Actors that provides the common functionality of actors.

    Example::

        class DaprActorInterface(ActorInterface):
            @actor_method(name="method")
            def method_invoke(self, arg: str) -> str:
                ...

        class DaprActor(Actor, DaprActorInterface):
            def __init__(self, ctx, actor_id):
                super(DaprActor, self).__init__(ctx, actor_id)

            def method_invoke(self, arg: str) -> str:
                return arg
            
            def _on_activate(self):
                pass

            def _on_deactivate(self):
                pass

    TODO: Support Timer, Reminder, State Management

    """

    def __init__(self, ctx: ActorRuntimeContext, actor_id: str):
        self.id = actor_id
        self._runtime_ctx = ctx
        self._dispatch_mapping = {}

    def on_activate_internal(self):
        # TODO: Reset state
        self._on_activate()

        # TODO: Save state modification

    def on_deactivate_internal(self):
        # TODO: Reset state
        self._on_deactivate()

    def _on_activate(self):
        """Override this method to initialize the members.
        
        This method is called right after the actor is activated and before
        any method call or reminders are dispatched on it.
        """
        pass

    def _on_deactivate(self):
        """Override this method to release any resources.
        
        This method is called when actor is deactivated (garbage collected
        by Actor Runtime). Actor operations like state changes should not
        be called from this method.
        """
        pass

    def on_pre_actor_method_internal(self, method_context: ActorMethodContext):
        self._on_pre_actor_method(method_context)

    def on_post_actor_method_internal(self, method_context: ActorMethodContext):
        self._on_post_actor_method(method_context)
        # TODO: Save state modification

    def on_invoke_failed(self, exception=None):
        # TODO: reset the state in state manager
        # (Exception has been thrown by user code)
        pass

    def _on_pre_actor_method(self, method_context: ActorMethodContext):
        """Override this method for performing any action prior to
        an actor method is invoked.
        
        This method is invoked by actor runtime just before invoking
        an actor method.

        This method is invoked by actor runtime prior to:
            - Invoking an actor interface method when a client request comes.
            - Invoking a method when a reminder fires.
            - Invoking a timer callback when timer fires.
        
        :param ActorMethodContext method_context: The method information
        """
        pass

    def _on_post_actor_method(self, method_context: ActorMethodContext):
        """Override this method for performing any action after
        an actor method has finished execution.
        
        This method is invoked by actor runtime an actor method has finished
        execution.

        This method is invoked by actor runtime after:
            - Invoking an actor interface method when a client request comes.
            - Invoking a method when a reminder fires.
            - Invoking a timer callback when timer fires.
        
        :param ActorMethodContext method_context: The method information
        """
        pass
