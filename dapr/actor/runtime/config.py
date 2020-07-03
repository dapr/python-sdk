# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from datetime import timedelta
from typing import Any, Dict, List, Optional


class ActorRuntimeConfig:
    """Actor runtime configuration that configures Actor behavior in
    Dapr Runtime.
    """

    def __init__(
            self,
            actor_idle_timeout: Optional[timedelta] = timedelta(hours=1),
            actor_scan_interval: Optional[timedelta] = timedelta(seconds=30),
            drain_ongoing_call_timeout: Optional[timedelta] = timedelta(minutes=1),
            drain_rebalanced_actors: Optional[bool] = True):
        """Inits :class:`ActorRuntimeConfig` to configure actors when dapr runtime starts.

        Args:
            actor_idle_timeout (datetime.timedelta): The timeout before deactivating an idle actor.
            actor_scan_interval (datetime.timedelta): The duration which specifies how often to scan
                for actors to deactivate idle actors. Actors that have been idle longer than
                actor_idle_timeout will be deactivated.
            drain_ongoing_call_timeout (datetime.timedelta): The duration when in the process of
                draining rebalanced actors. This specifies the timeout for the current active actor
                method to finish. If there is no current actor method call, this is ignored.
            drain_rebalanced_actors (bool): If true, Dapr will wait for drain_ongoing_call_timeout
                to allow a current actor call to complete before trying to deactivate an actor.
        """
        self._entities: List[str] = []
        self._actor_idle_timeout = actor_idle_timeout
        self._actor_scan_interval = actor_scan_interval
        self._drain_ongoing_call_timeout = drain_ongoing_call_timeout
        self._drain_rebalanced_actors = drain_rebalanced_actors

    def update_entities(self, entities: List[str]) -> None:
        """Updates actor types in entities property.

        Args:
            entities (List[str]): the list of actor type names
        """
        self._entities = entities or []

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorRuntimeConfig as a dict."""
        return {
            'entities': self._entities,
            'actorIdleTimeout': self._actor_idle_timeout,
            'actorScanInterval': self._actor_scan_interval,
            'drainOngoingCallTimeout': self._drain_ongoing_call_timeout,
            'drainRebalancedActors': self._drain_rebalanced_actors,
        }
