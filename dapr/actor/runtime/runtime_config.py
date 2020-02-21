# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from datetime import timedelta
import json

class ActorRuntimeConfig(object):
    """Actor runtime configuration that configures Actor behavior in
    Dapr Runtime.
    """
    
    def __init__(
            self, drain_rebalanced_actors=True,
            actor_idle_timeout=timedelta(hours=1),
            actor_scan_interval=timedelta(seconds=30),
            drain_ongoing_call_timeout=timedelta(minutes=1)):
        
        self.entities = []
        self.actorIdleTimeout = actor_idle_timeout
        self.actorScanInterval = actor_scan_interval
        self.drainOngoingCallTimeout = drain_ongoing_call_timeout
        self.drainRebalancedActors = drain_rebalanced_actors

    def update_entities(self, entities: list):
        self.entities = entities or []

    def __repr__(self):
        return json.dumps(self.__dict__)