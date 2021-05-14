# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

import contextvars

reentrancy_ctx = contextvars.ContextVar("reentrancy_ctx")
