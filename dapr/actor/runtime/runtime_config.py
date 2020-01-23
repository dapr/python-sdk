# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from .runtime import ActorRuntime

class ActorRuntimeConfig(object):
    def __init__(
        self,
        drain_rebalanced_actors=True,
        actor_idle_timeout_in_second=3600,
        actor_scan_interval_in_second=30,
        drain_ongoing_call_timeout_in_second=60):

        self.actor_idle_timeout_in_second=actor_idle_timeout_in_second
        self.actor_scan_interval_in_second = actor_scan_interval_in_second
        self.drain_ongoing_call_timeout_in_second = drain_ongoing_call_timeout_in_second
        self.drain_rebalanced_actors = drain_rebalanced_actors

    @property
    def data(self):
        return {
            'entities': ActorRuntime.get_registered_actor_types(),
            'actorIdleTimeout': '{}s'.format(self.actor_idle_timeout_in_second),
            'actorScanInterval': '{}s'.format(self.actor_scan_interval_in_second),
            'drainOngoingCallTimeout': '{}s'.format(self.drain_ongoing_call_timeout_in_second),
            'drainRebalancedActors': self.drain_rebalanced_actors
        }
    
    def to_json(self) -> str:
        return json.dumps(self.data)