# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from datetime import timedelta
from typing import Any, Dict, List, Optional, Set


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


class PubsubConfig:
    def __init__(
            self,
            pubsubName: str,
            topic: str,
            actorType: str,
            method: str,
            actorIdDataAttribute: str = ""):

        """Inits :class:`PubsubConfig` to configure Actor pubsub.

        Args:
            pubsubName (str): The name of the pubsub to subscribe.
            topic (str): The name of the Topic to subscribe.
            actorType (str): The actor type that will be called
            method (str): Method of the actor type that will be requested
            actorIdDataAttribute (str): Id for existing consumer groups
        """

        self._pubsubName = pubsubName
        self._topic = topic
        self._actorType = actorType
        self._method = method
        self._actorIdDataAttribute = actorIdDataAttribute

    def as_dict(self) -> Dict[str, Any]:
        """Returns PubsubConfig as a dict."""
        return {
            'pubsubName': self._pubsubName,
            'topic': self._topic,
            'actorType': self._actorType,
            'method': self._method,
            'actorIdDataAttribute': self._actorIdDataAttribute
        }


class ActorTypeConfig:
    """Per Actor Type Configuration that configures Actor behavior for a specific Actor Type in
    Dapr Runtime.
    """

    def __init__(
            self,
            actor_type: str,
            actor_idle_timeout: Optional[timedelta] = None,
            actor_scan_interval: Optional[timedelta] = None,
            drain_ongoing_call_timeout: Optional[timedelta] = None,
            drain_rebalanced_actors: Optional[bool] = None,
            reentrancy: Optional[ActorReentrancyConfig] = None,
            reminders_storage_partitions: Optional[int] = None):
        """Inits :class:`ActorTypeConfig` to configure the behavior of a specific actor type
        when dapr runtime starts.

        Args:
            actor_type (str): Actor type.
            actor_idle_timeout (datetime.timedelta): The timeout before deactivating an idle actor.
            actor_scan_interval (datetime.timedelta): The duration which specifies how often to scan
                for actors to deactivate idle actors. Actors that have been idle longer than
                actor_idle_timeout will be deactivated.
            drain_ongoing_call_timeout (datetime.timedelta): The duration which specifies the
                timeout for the current active actor method to finish before actor deactivation.
                If there is no current actor method call, this is ignored.
            drain_rebalanced_actors (bool): If true, Dapr will wait for drain_ongoing_call_timeout
                to allow a current actor call to complete before trying to deactivate an actor.
            reentrancy (ActorReentrancyConfig): Configure the reentrancy behavior for an actor.
                If not provided, reentrancy is diabled.
            reminders_storage_partitions (int): The number of partitions to use for reminders
                storage.
        """
        self._actor_type = actor_type
        self._actor_idle_timeout = actor_idle_timeout
        self._actor_scan_interval = actor_scan_interval
        self._drain_ongoing_call_timeout = drain_ongoing_call_timeout
        self._drain_rebalanced_actors = drain_rebalanced_actors
        self._reentrancy = reentrancy
        self._reminders_storage_partitions = reminders_storage_partitions

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorTypeConfig as a dict."""

        configDict: Dict[str, Any] = dict()
        configDict['entities'] = [self._actor_type]

        if self._actor_idle_timeout is not None:
            configDict.update({'actorIdleTimeout': self._actor_idle_timeout})

        if self._actor_scan_interval is not None:
            configDict.update({'actorScanInterval': self._actor_scan_interval})

        if self._drain_ongoing_call_timeout is not None:
            configDict.update({'drainOngoingCallTimeout': self._drain_ongoing_call_timeout})

        if self._drain_rebalanced_actors is not None:
            configDict.update({'drainRebalancedActors': self._drain_rebalanced_actors})

        if self._reentrancy:
            configDict.update({'reentrancy': self._reentrancy.as_dict()})

        if self._reminders_storage_partitions:
            configDict.update(
                {'remindersStoragePartitions': self._reminders_storage_partitions})

        return configDict


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
            pubsub: List[PubsubConfig] = [],
            reminders_storage_partitions: Optional[int] = None,
            actor_type_configs: List[ActorTypeConfig] = []):
        """Inits :class:`ActorRuntimeConfig` to configure actors when dapr runtime starts.

        Args:
            actor_idle_timeout (datetime.timedelta): The timeout before deactivating an idle actor.
            actor_scan_interval (datetime.timedelta): The duration which specifies how often to scan
                for actors to deactivate idle actors. Actors that have been idle longer than
                actor_idle_timeout will be deactivated.
            drain_ongoing_call_timeout (datetime.timedelta): The duration which specifies the
                timeout for the current active actor method to finish before actor deactivation.
                If there is no current actor method call, this is ignored.
            drain_rebalanced_actors (bool): If true, Dapr will wait for drain_ongoing_call_timeout
                to allow a current actor call to complete before trying to deactivate an actor.
            reentrancy (ActorReentrancyConfig): Configure the reentrancy behavior for an actor.
                If not provided, reentrancy is diabled.
            pubsub (List[PubsubConfig]): Configure the pubsub data to subscribe.
                If there is not pubsub configuration, pubsub is empty
            reminders_storage_partitions (int): The number of partitions to use for reminders
                storage.
            actor_type_configs (List[ActorTypeConfig]): Configure the behavior of specific
                actor types.
        """
        self._entities: Set[str] = set()
        self._actor_idle_timeout = actor_idle_timeout
        self._actor_scan_interval = actor_scan_interval
        self._drain_ongoing_call_timeout = drain_ongoing_call_timeout
        self._drain_rebalanced_actors = drain_rebalanced_actors
        self._reentrancy = reentrancy
        self._pubsub: List[PubsubConfig] = pubsub
        self._reminders_storage_partitions = reminders_storage_partitions
        self._entitiesConfig: List[ActorTypeConfig] = actor_type_configs

    def update_entities(self, entities: List[str]) -> None:
        """Updates actor types in entities property.

        Args:
            entities (List[str]): the list of actor type names
        """
        self._entities.update(entities)

    def update_actor_type_configs(self, actor_type_configs: List[ActorTypeConfig]) -> None:
        """Updates actor type configs.

        Args:
            actor_type_configs (List[ActorTypeConfig]): the list of actor type configs
        """
        self._entitiesConfig = actor_type_configs or []

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorRuntimeConfig as a dict."""

        entities: Set[str] = self._entities

        configDict: Dict[str, Any] = {
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

        configDict['pubsub'] = []
        for pubsubConf in self._pubsub:
            configDict['pubsub'].append(pubsubConf.as_dict())

        configDict['entitiesConfig'] = []
        for entityConfig in self._entitiesConfig:
            configDict['entitiesConfig'].append(entityConfig.as_dict())
            entities.add(entityConfig._actor_type)

        configDict['entities'] = list(entities)

        return configDict
