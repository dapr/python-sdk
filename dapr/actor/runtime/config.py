# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from datetime import timedelta


class ActorRuntimeConfig:
    """Actor runtime configuration that configures Actor behavior in
    Dapr Runtime.
    """

    def __init__(
            self, drain_rebalanced_actors=True,
            actor_idle_timeout=timedelta(hours=1),
            actor_scan_interval=timedelta(seconds=30),
            drain_ongoing_call_timeout=timedelta(minutes=1)):
        self._entities = []
        self._actor_idle_timeout = actor_idle_timeout
        self._actor_scan_interval = actor_scan_interval
        self._drain_ongoing_call_timeout = drain_ongoing_call_timeout
        self._drain_rebalanced_actors = drain_rebalanced_actors

    def update_entities(self, entities: list):
        """Updates actor types in entities property.

        :param list entities: list of actor type names
        """
        self._entities = entities or []

    def as_dict(self):
        return {
            'entities': self._entities,
            'actorIdleTimeout': self._actor_idle_timeout,
            'actorScanInterval': self._actor_scan_interval,
            'drainOngoingCallTimeout': self._drain_ongoing_call_timeout,
            'drainRebalancedActors': self._drain_rebalanced_actors,
        }
