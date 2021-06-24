# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

from typing import Optional
from contextvars import ContextVar

reentrancy_ctx: ContextVar[Optional[str]] = ContextVar("reentrancy_ctx", default=None)
