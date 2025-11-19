# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

from __future__ import annotations

import json
from collections.abc import MutableMapping, MutableSequence
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Protocol,
    cast,
)

"""
General-purpose, provider-agnostic JSON serialization helpers for workflow activities.

This module focuses on generic extension points to ensure activity inputs/outputs are JSON-only
and replay-safe. It intentionally avoids provider-specific shapes (e.g., model/tool contracts),
which should live in examples or external packages.
"""


def _is_json_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _to_json_safe(value: Any, *, strict: bool) -> Any:
    """Convert a Python object to a JSON-serializable structure.

    - Dict keys become strings (lenient) or error (strict) if not str.
    - Unsupported values become str(value) (lenient) or error (strict).
    """

    if _is_json_primitive(value):
        return value

    if isinstance(value, MutableSequence) or isinstance(value, tuple):
        return [_to_json_safe(v, strict=strict) for v in value]

    if isinstance(value, MutableMapping) or isinstance(value, dict):
        output: Dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                if strict:
                    raise ValueError('dict keys must be strings in strict mode')
                k = str(k)
            output[k] = _to_json_safe(v, strict=strict)
        return output

    if strict:
        # Attempt final json.dumps to surface type
        try:
            json.dumps(value)
        except Exception as err:
            raise ValueError(f'non-JSON-serializable value: {type(value).__name__}') from err
        return value

    return str(value)


def _ensure_json(obj: Any, *, strict: bool) -> Any:
    converted = _to_json_safe(obj, strict=strict)
    # json.dumps as a final guard
    json.dumps(converted)
    return converted


# ----------------------------------------------------------------------------------------------
# Generic helpers and extension points
# ----------------------------------------------------------------------------------------------


class CanonicalSerializable(Protocol):
    """Objects implementing this can produce a canonical JSON-serializable structure."""

    def to_canonical_json(self, *, strict: bool = True) -> Any:
        ...


class GenericSerializer(Protocol):
    """Serializer that converts arbitrary Python objects to/from JSON-serializable data."""

    def serialize(self, obj: Any, *, strict: bool = True) -> Any:
        ...

    def deserialize(self, data: Any) -> Any:
        ...


_SERIALIZERS: Dict[str, GenericSerializer] = {}


def register_serializer(name: str, serializer: GenericSerializer) -> None:
    if not name:
        raise ValueError('serializer name must be non-empty')
    _SERIALIZERS[name] = serializer


def get_serializer(name: str) -> Optional[GenericSerializer]:
    return _SERIALIZERS.get(name)


def ensure_canonical_json(obj: Any, *, strict: bool = True) -> Any:
    """Ensure any object is converted into a JSON-serializable structure.

    - If the object implements CanonicalSerializable, call to_canonical_json
    - Else, coerce via the internal JSON-safe conversion
    """

    if hasattr(obj, 'to_canonical_json') and callable(getattr(obj, 'to_canonical_json')):
        return _ensure_json(
            cast(CanonicalSerializable, obj).to_canonical_json(strict=strict), strict=strict
        )
    return _ensure_json(obj, strict=strict)


class ActivityIOAdapter(Protocol):
    """Adapter to control how activity inputs/outputs are serialized."""

    def serialize_input(self, input: Any, *, strict: bool = True) -> Any:
        ...

    def serialize_output(self, output: Any, *, strict: bool = True) -> Any:
        ...


_ACTIVITY_ADAPTERS: Dict[str, ActivityIOAdapter] = {}


def register_activity_adapter(name: str, adapter: ActivityIOAdapter) -> None:
    if not name:
        raise ValueError('activity adapter name must be non-empty')
    _ACTIVITY_ADAPTERS[name] = adapter


def get_activity_adapter(name: str) -> Optional[ActivityIOAdapter]:
    return _ACTIVITY_ADAPTERS.get(name)


def use_activity_adapter(
    adapter: ActivityIOAdapter,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to attach an ActivityIOAdapter to an activity function."""

    def _decorate(f: Callable[..., Any]) -> Callable[..., Any]:
        cast(Any, f).__dapr_activity_io_adapter__ = adapter
        return f

    return _decorate


def serialize_activity_input(func: Callable[..., Any], input: Any, *, strict: bool = True) -> Any:
    adapter = getattr(func, '__dapr_activity_io_adapter__', None)
    if adapter:
        return cast(ActivityIOAdapter, adapter).serialize_input(input, strict=strict)
    return ensure_canonical_json(input, strict=strict)


def serialize_activity_output(func: Callable[..., Any], output: Any, *, strict: bool = True) -> Any:
    adapter = getattr(func, '__dapr_activity_io_adapter__', None)
    if adapter:
        return cast(ActivityIOAdapter, adapter).serialize_output(output, strict=strict)
    return ensure_canonical_json(output, strict=strict)
