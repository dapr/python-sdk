# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from datetime import timedelta
from .runtime import ActorRuntime

class ActorRuntimeConfig(object):
    def __init__(
        self,
        drain_rebalanced_actors=True,
        actor_idle_timeout=timedelta(hours=1),
        actor_scan_interval=timedelta(seconds=30),
        drain_ongoing_call_timeout=timedelta(minutes=1)):

        self.actorIdleTimeout = actor_idle_timeout
        self.actorScanInterval = actor_scan_interval
        self.drainOngoingCallTimeout = drain_ongoing_call_timeout
        self.drainRebalancedActors = drain_rebalanced_actors

    @property
    def entities(self):
        return ActorRuntime.get_registered_actor_types()
    
    def __repr__(self):
        return json.dumps(self.__dict__)