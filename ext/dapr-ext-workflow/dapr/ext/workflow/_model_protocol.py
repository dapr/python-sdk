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

from __future__ import annotations

import inspect
import typing
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, Callable, Optional

# A "model" here is anything that implements the Pydantic v2 shape:
#   - model_dump(self, ...) -> dict
#   - cls.model_validate(value) -> instance
# We duck-type on these names rather than importing pydantic so the SDK has no
# hard dependency on pydantic (or any specific version of it). SQLModel,
# FastAPI response models, and custom classes mirroring the protocol all work.


def is_model(obj: Any) -> bool:
    """Whether obj implements the model protocol (model_dump + model_validate)."""
    return is_model_class(type(obj))


def is_model_class(cls: Any) -> bool:
    """Whether cls is a class implementing the model protocol."""
    return (
        inspect.isclass(cls)
        and callable(getattr(cls, 'model_dump', None))
        and callable(getattr(cls, 'model_validate', None))
    )


@lru_cache(maxsize=None)
def _supports_mode_kwarg(cls: type) -> bool:
    """Whether cls.model_dump accepts a `mode` keyword (Pydantic v2 signature)."""
    try:
        sig = inspect.signature(cls.model_dump)
    except (TypeError, ValueError):
        return False
    params = sig.parameters
    if 'mode' in params:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


def dump_model(model: Any) -> Any:
    """Serialize a model instance to a JSON-compatible primitive graph.

    Prefers model_dump(mode='json') when supported so nested datetimes, enums,
    and UUIDs render into JSON-safe primitives. Falls back to bare model_dump()
    for protocol-compatible classes that don't accept the mode kwarg — those
    classes are responsible for returning JSON-safe values themselves.
    """
    if not is_model(model):
        raise TypeError(
            f'Expected a model-like object with model_dump/model_validate, '
            f'got {type(model).__name__}'
        )
    cls = type(model)
    if _supports_mode_kwarg(cls):
        return model.model_dump(mode='json')
    return model.model_dump()


def coerce_to_model(value: Any, cls: type) -> Any:
    """Reconstruct a model instance from a decoded JSON payload.

    Accepts dicts, SimpleNamespace (from the InternalJSONDecoder's
    AUTO_SERIALIZED path), or already-instantiated models. Any other shape
    raises TypeError so the failure surfaces at the activity/workflow
    boundary rather than later as an attribute access error.
    """
    if not is_model_class(cls):
        raise TypeError(f'{cls!r} is not a model class (no model_dump/model_validate)')
    if isinstance(value, cls):
        return value
    if isinstance(value, SimpleNamespace):
        value = vars(value)
    if isinstance(value, dict):
        return cls.model_validate(value)
    raise TypeError(
        f'Cannot coerce value of type {type(value).__name__} into {cls.__name__}; '
        'expected a dict, SimpleNamespace, or existing model instance.'
    )


def resolve_input_model(fn: Callable[..., Any]) -> Optional[type]:
    """Return the model class annotated on fn's input parameter, if any.

    Workflow and activity functions take (ctx, input) — we look at the second
    positional parameter's annotation. Returns None when no annotation is
    present or the annotation is not a model class. Optional[Model] and
    Model | None are unwrapped to Model.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None

    params = list(sig.parameters.values())
    if len(params) < 2:
        return None

    annotation = params[1].annotation
    if annotation is inspect.Parameter.empty:
        return None

    if isinstance(annotation, str):
        try:
            hints = typing.get_type_hints(fn)
            annotation = hints.get(params[1].name, annotation)
        except Exception:
            return None

    annotation = _unwrap_optional(annotation)
    return annotation if is_model_class(annotation) else None


def _unwrap_optional(annotation: Any) -> Any:
    """Unwrap Optional[X] / X | None to X. Leaves other annotations unchanged."""
    origin = typing.get_origin(annotation)
    if origin is typing.Union or _is_pep604_union(origin):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _is_pep604_union(origin: Any) -> bool:
    try:
        from types import UnionType  # type: ignore[attr-defined]

        return origin is UnionType
    except ImportError:
        return False
