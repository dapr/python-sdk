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

# `dapr.ext.workflow`'s automatic activity input/output coercion
# (`dapr.ext.workflow._model_protocol`) only recognizes Pydantic-v2-shaped
# classes (objects exposing `model_dump` / `model_validate`). This package
# uses plain `@dataclass` types everywhere instead, matching the dataclass
# style used across the rest of the SDK (see `dapr/clients/grpc/_jobs.py`,
# `dapr/ext/workflow/propagation.py`) rather than adding a new hard runtime
# dependency on pydantic. A plain dataclass passed as `call_activity(...,
# input=...)` therefore arrives on the other side undecoded, as a `dict` or
# `SimpleNamespace` -- these two helpers perform that conversion explicitly at
# each activity/workflow boundary.
#
# Every dataclass that crosses an activity boundary must be *flat* (fields are
# JSON primitives, or lists/dicts of them): `dataclasses.asdict` recurses into
# nested dataclass fields on the way out, but `from_wire` does not reconstruct
# them on the way back, so a nested dataclass field would come back as a plain
# dict instead of an instance. Richer nested models (e.g. `SourceDocument`)
# are used only within a single activity's body, never as its input/output.

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Any, Mapping, TypeVar

T = TypeVar('T')


def to_wire(value: Any) -> Any:
    """Serializes a flat dataclass instance to a JSON-safe dict.

    Args:
        value: A dataclass instance, or any already-JSON-safe value.

    Returns:
        `dataclasses.asdict(value)` if `value` is a dataclass instance,
        otherwise `value` unchanged.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return value


def from_wire(raw: Any, cls: type[T]) -> T:
    """Reconstructs a flat dataclass instance from a decoded activity payload.

    Args:
        raw: The value durabletask handed to the activity/workflow: typically
            a `dict`, occasionally a `SimpleNamespace`, or already an
            instance of `cls` (e.g. when called directly from a unit test).
        cls: The flat dataclass type to reconstruct.

    Returns:
        An instance of `cls`.

    Raises:
        TypeError: `raw` is not a dict, SimpleNamespace, or `cls` instance.
    """
    if isinstance(raw, cls):
        return raw
    if isinstance(raw, SimpleNamespace):
        raw = vars(raw)
    if isinstance(raw, Mapping):
        return cls(**raw)
    raise TypeError(
        f'Cannot interpret {type(raw).__name__!r} as {cls.__name__}; expected a dict, '
        'SimpleNamespace, or existing instance.'
    )
