# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from datetime import timedelta
from typing import Any, Dict, List, Optional


class ActorReentrancyConfig:
    def __init__(
            self,
            enabled: bool = False,
            maxStackDepth: int = 32):
        """Inits :class:`ActorReentrancyConfig` to optionally configure actor
        reentrancy.

        Args:
            enabled (bool): Set to enable or disable reentrancy.
            maxStackDepth (int): Limit for the number of concurrent reentrant requests
                to an actor, further requests are denied.
        """

        self._enabled = enabled
        self._maxStackDepth = maxStackDepth

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorReentrancyConfig as a dict."""
        return {
            'enabled': self._enabled,
            'maxStackDepth': self._maxStackDepth,
        }


class ActorRuntimeConfig:
    """Actor runtime configuration that configures Actor behavior in
    Dapr Runtime.
    """

    def __init__(
            self,
            actor_idle_timeout: Optional[timedelta] = timedelta(hours=1),
            actor_scan_interval: Optional[timedelta] = timedelta(seconds=30),
            drain_ongoing_call_timeout: Optional[timedelta] = timedelta(minutes=1),
            drain_rebalanced_actors: Optional[bool] = True,
            reentrancy: Optional[ActorReentrancyConfig] = None,
            reminders_storage_partitions: Optional[int] = None):
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
            reentrancy (ActorReentrancyConfig): Configure the reentrancy behavior for an actor.
                If not provided, reentrancy is diabled.
            reminders_storage_partitions (int): The number of partitions to use for reminders
                storage.
        """
        self._entities: List[str] = []
        self._actor_idle_timeout = actor_idle_timeout
        self._actor_scan_interval = actor_scan_interval
        self._drain_ongoing_call_timeout = drain_ongoing_call_timeout
        self._drain_rebalanced_actors = drain_rebalanced_actors
        self._reentrancy = reentrancy
        self._reminders_storage_partitions = reminders_storage_partitions

    def update_entities(self, entities: List[str]) -> None:
        """Updates actor types in entities property.

        Args:
            entities (List[str]): the list of actor type names
        """
        self._entities = entities or []

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorRuntimeConfig as a dict."""

        configDict: Dict[str, Any] = {
            'entities': self._entities,
            'actorIdleTimeout': self._actor_idle_timeout,
            'actorScanInterval': self._actor_scan_interval,
            'drainOngoingCallTimeout': self._drain_ongoing_call_timeout,
            'drainRebalancedActors': self._drain_rebalanced_actors,
        }

        if self._reentrancy:
            configDict.update({'reentrancy': self._reentrancy.as_dict()})

        if self._reminders_storage_partitions:
            configDict.update(
                {'remindersStoragePartitions': self._reminders_storage_partitions})

        return configDict
