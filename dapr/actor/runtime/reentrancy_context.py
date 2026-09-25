# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

# Backwards-compatible alias. The reentrancy context moved to dapr.common so
# the actor clients (dapr.clients) can import it without a circular dependency
# on dapr.actor; existing imports of this path keep working.
from dapr.common.reentrancy_context import reentrancy_ctx

__all__ = ['reentrancy_ctx']
