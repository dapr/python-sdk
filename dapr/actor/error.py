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


class ActorNotFoundError(Exception):
    """Base for callbacks whose addressable target does not exist.

    Both subclasses are mapped to gRPC ``NOT_FOUND`` by the gRPC actor host so
    daprd treats them as permanent, non-retryable failures — matching how the
    HTTP transport surfaces an unknown actor type or method. Catch this base to
    handle either case, or a subclass for the specific one.
    """


class ActorTypeNotFoundError(ActorNotFoundError):
    """Raised when a callback targets an actor type the host does not host."""


class ActorMethodNotFoundError(ActorNotFoundError, AttributeError):
    """Raised when dispatching a method the actor type does not define.

    Also subclasses :class:`AttributeError` for backwards compatibility (the
    method dispatcher historically raised a bare ``AttributeError``), while
    letting callers distinguish a missing actor method from an
    ``AttributeError`` raised inside the actor's own code.
    """
