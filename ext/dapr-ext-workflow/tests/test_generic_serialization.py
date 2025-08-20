from dataclasses import dataclass
from typing import Any

from dapr.ext.workflow import (
    CanonicalSerializable,
    ensure_canonical_json,
    use_activity_adapter,
    serialize_activity_input,
    serialize_activity_output,
    ActivityIOAdapter,
)


@dataclass
class _Point(CanonicalSerializable):
    x: int
    y: int

    def to_canonical_json(self, *, strict: bool = True) -> Any:
        return {'x': self.x, 'y': self.y}


def test_ensure_canonical_json_on_custom_object():
    p = _Point(1, 2)
    out = ensure_canonical_json(p, strict=True)
    assert out == {'x': 1, 'y': 2}


class _IO(ActivityIOAdapter):
    def serialize_input(self, input: Any, *, strict: bool = True) -> Any:
        if isinstance(input, _Point):
            return {'pt': [input.x, input.y]}
        return ensure_canonical_json(input, strict=strict)

    def serialize_output(self, output: Any, *, strict: bool = True) -> Any:
        return {'ok': ensure_canonical_json(output, strict=strict)}


def test_activity_adapter_decorator_customizes_io():
    _use = use_activity_adapter(_IO())
    @_use
    def act(obj):
        return obj

    pt = _Point(3, 4)
    inp = serialize_activity_input(act, pt, strict=True)
    assert inp == {'pt': [3, 4]}

    out = serialize_activity_output(act, {'k': 'v'}, strict=True)
    assert out == {'ok': {'k': 'v'}}


