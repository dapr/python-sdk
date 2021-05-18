# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from typing import Any, Dict, Optional


class ActorReentrancyConfig:
    def __init__(
            self,
            enabled: Optional[bool] = False,
            limit: Optional[int] = 32):
        """Inits :class:`ActorReentrancyConfig` to optionally configure actor
        reentrancy.

        Args:
            enabled (bool): Set to enable or disable reentrancy.
            limit (int): Limit for the number of concurrent reentrant requests
                to an actor, further requests are denied.
        """

        self._enabled = enabled
        self._limit = limit

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorReentrancyConfig as a dict."""
        return {
            'enabled': self._enabled,
            'limit': self._limit,
        }
