# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from typing import Any, Dict, List, Optional


class ActorReentrancyConfig:
    def __init__(
            self,
            enabled: Optional[bool] = False,
            methods: Optional[List[str]] = [],
            limit: Optional[int] = 32):
        """Inits :class:`ActorReentrancyConfig` to optionally configure actor
        reentrancy.

        Args:
            enabled (bool): Set to enable or disable reentrancy.
            methods (list[str]): Filter specifying allowed methods, ignored if
                empty/omitted.
            limit (int): Limit for the number of concurrent reentrant requests
                to an actor, further requests are denied.
        """

        self._enabled = enabled
        self._methods = methods
        self._limit = limit

    def as_dict(self) -> Dict[str, Any]:
        """Returns ActorReentrancyConfig as a dict."""
        return {
            'enabled': self._enabled,
            'methods': self._methods,
            'limit': self._limit,
        }
