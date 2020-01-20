# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import threading

from dapr.actor import DaprActorClientBase
from .http.dapr_actor_http_client import DaprActorHttpClient

class DaprActorClient(object):

    _client_lock = threading.Lock()
    @classmethod
    def createOrGetClient(cls, options = {}) -> DaprActorClientBase:
        with cls._client_lock:
            if cls._client_lock is None:
                cls._client = DaprActorHttpClient()

        return cls._client
