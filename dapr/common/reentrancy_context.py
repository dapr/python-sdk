# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

from contextvars import ContextVar
from typing import Optional

# The actor reentrancy id (Dapr-Reentrancy-Id) is shared between the actor
# runtime (dapr.actor) and the actor clients (dapr.clients). It lives in this
# neutral leaf module so both can import it at the top level: dapr.clients
# eagerly imports the actor HTTP client and dapr.actor imports it back, so an
# import of dapr.actor from within dapr.clients would be circular.
reentrancy_ctx: ContextVar[Optional[str]] = ContextVar('reentrancy_ctx', default=None)
