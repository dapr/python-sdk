# -*- coding: utf-8 -*-
"""
Additional targeted unit tests to increase coverage of
_dapr.clients.grpc._conversation_helpers.
"""
import base64
import json
import unittest
import warnings
from dataclasses import dataclass
from typing import List, Literal, Optional, Any, Dict, Union

from dapr.conf import settings
from dapr.clients.grpc._conversation_helpers import (
    ToolArgumentError,
    _python_type_to_json_schema,
    bind_params_to_func,
    stringify_tool_output,
)

from enum import Enum


class TestLargeEnumBehavior(unittest.TestCase):
    def setUp(self):
        # Save originals
        self._orig_max = settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS
        self._orig_beh = settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR

    def tearDown(self):
        # Restore
        settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS = self._orig_max
        settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR = self._orig_beh

    def test_large_enum_compacted_to_string(self):
        # Make threshold tiny to trigger large-enum path
        settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS = 2
        settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR = 'string'

        class BigEnum(Enum):
            A = 'a'
            B = 'b'
            C = 'c'
            D = 'd'

        schema = _python_type_to_json_schema(BigEnum)
        # Should be compacted to string with description and examples
        self.assertEqual(schema.get('type'), 'string')
        self.assertIn('description', schema)
        self.assertIn('examples', schema)
        self.assertTrue(len(schema['examples']) > 0)

    def test_large_enum_error_mode(self):
        settings.DAPR_CONVERSATION_TOOLS_MAX_ENUM_ITEMS = 1
        settings.DAPR_CONVERSATION_TOOLS_LARGE_ENUM_BEHAVIOR = 'error'

        from enum import Enum

        class BigEnum(Enum):
            A = 'a'
            B = 'b'

        with self.assertRaises(ValueError):
            _python_type_to_json_schema(BigEnum)


class TestCoercionsAndBinding(unittest.TestCase):
    def test_coerce_bool_variants(self):
        def f(flag: bool) -> bool:
            return flag

        # True-ish variants
        for v in ['true', 'True', 'YES', '1', 'on', ' y ']:
            bound = bind_params_to_func(f, {'flag': v})
            self.assertIs(f(*bound.args, **bound.kwargs), True)

        # False-ish variants
        for v in ['false', 'False', 'NO', '0', 'off', ' n ']:
            bound = bind_params_to_func(f, {'flag': v})
            self.assertIs(f(*bound.args, **bound.kwargs), False)

        # Invalid
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'flag': 'maybe'})

    def test_literal_numeric_from_string(self):
        def g(x: Literal[1, 2, 3]) -> int:
            return x  # type: ignore[return-value]

        bound = bind_params_to_func(g, {'x': '2'})
        self.assertEqual(g(*bound.args, **bound.kwargs), 2)

    def test_unexpected_kwarg_is_rejected(self):
        def h(a: int) -> int:
            return a

        with self.assertRaises(Exception):
            bind_params_to_func(h, {'a': 1, 'extra': 2})

    def test_dataclass_arg_validation(self):
        @dataclass
        class P:
            x: int
            y: str

        def k(p: P) -> str:
            return p.y

        # Passing an instance is fine
        p = P(1, 'ok')
        bound = bind_params_to_func(k, {'p': p})
        self.assertEqual(k(*bound.args, **bound.kwargs), 'ok')

        # Passing a dict should fail for dataclass per implementation
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(k, {'p': {'x': 1, 'y': 'nope'}})


class TestPlainClassSchema(unittest.TestCase):
    def test_plain_class_init_signature(self):
        class C:
            def __init__(self, a: int, b: str = 'x'):
                self.a = a
                self.b = b

        schema = _python_type_to_json_schema(C)
        self.assertEqual(schema['type'], 'object')
        props = schema['properties']
        self.assertIn('a', props)
        self.assertIn('b', props)
        # Only 'a' is required
        self.assertIn('required', schema)
        self.assertEqual(schema['required'], ['a'])

    def test_plain_class_slots_fallback(self):
        class D:
            __slots__ = ('m', 'n')
            m: int
            n: Optional[str]

        schema = _python_type_to_json_schema(D)
        # Implementation builds properties from __slots__ with required for non-optional
        self.assertEqual(schema['type'], 'object')
        self.assertIn('properties', schema)
        self.assertIn('m', schema['properties'])
        self.assertIn('n', schema['properties'])
        self.assertEqual(schema['properties']['m']['type'], 'integer')
        self.assertEqual(schema['properties']['n']['type'], 'string')
        self.assertIn('required', schema)
        self.assertEqual(schema['required'], ['m'])


class TestDocstringUnsupportedWarning(unittest.TestCase):
    def test_informal_param_info_warning(self):
        def unsupported(x: int, y: str):
            """Do something.

            The x parameter should be an integer indicating repetitions. The y parameter is used for labeling.
            """
            return x, y

        # _extract_docstring_args is used via function_to_json_schema or directly. Use direct import path
        from dapr.clients.grpc._conversation_helpers import _extract_docstring_args

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            res = _extract_docstring_args(unsupported)
            self.assertEqual(res, {})
            self.assertTrue(
                any('appears to contain parameter information' in str(wi.message) for wi in w)
            )


class TestLiteralSchemaMapping(unittest.TestCase):
    def test_literal_strings_schema(self):
        T = Literal['a', 'b', 'c']
        schema = _python_type_to_json_schema(T)
        self.assertEqual(schema.get('type'), 'string')
        self.assertEqual(set(schema['enum']), {'a', 'b', 'c'})

    def test_literal_ints_schema(self):
        T = Literal[1, 2, 3]
        schema = _python_type_to_json_schema(T)
        self.assertEqual(schema.get('type'), 'integer')
        self.assertEqual(set(schema['enum']), {1, 2, 3})

    def test_literal_nullable_string_schema(self):
        T = Literal[None, 'x', 'y']
        schema = _python_type_to_json_schema(T)
        # non-null types only string, should set 'type' to 'string' and include None in enum
        self.assertEqual(schema.get('type'), 'string')
        self.assertIn(None, schema['enum'])
        self.assertIn('x', schema['enum'])
        self.assertIn('y', schema['enum'])

    def test_literal_mixed_types_no_unified_type(self):
        T = Literal['x', 1]
        schema = _python_type_to_json_schema(T)
        # Mixed non-null types -> no unified 'type' should be set
        self.assertNotIn('type', schema)
        self.assertEqual(set(schema['enum']), {'x', 1})

    def test_literal_enum_members_normalized(self):
        from enum import Enum

        class Mode(Enum):
            FAST = 'fast'
            SLOW = 'slow'

        T = Literal[Mode.FAST, Mode.SLOW]
        schema = _python_type_to_json_schema(T)
        self.assertEqual(schema.get('type'), 'string')
        self.assertEqual(set(schema['enum']), {'fast', 'slow'})

    def test_literal_bytes_and_bytearray_schema(self):
        T = Literal[b'a', bytearray(b'b')]
        schema = _python_type_to_json_schema(T)
        # bytes/bytearray are coerced to string type for schema typing
        self.assertEqual(schema.get('type'), 'string')
        # The enum preserves the literal values as provided
        self.assertIn(b'a', schema['enum'])
        self.assertIn(bytearray(b'b'), schema['enum'])


# --- Helpers for Coercion tests


class Mode(Enum):
    RED = 'red'
    BLUE = 'blue'


@dataclass
class DC:
    x: int
    y: str


class Plain:
    def __init__(self, a: int, b: str = 'x') -> None:
        self.a = a
        self.b = b


class TestScalarCoercions(unittest.TestCase):
    def test_int_from_str_and_float_and_invalid(self):
        def f(a: int) -> int:
            return a

        # str -> int
        bound = bind_params_to_func(f, {'a': ' 42 '})
        self.assertEqual(f(*bound.args, **bound.kwargs), 42)

        # float integral -> int
        bound = bind_params_to_func(f, {'a': 3.0})
        self.assertEqual(f(*bound.args, **bound.kwargs), 3)

        # float non-integral -> error
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'a': 3.14})

    def test_float_from_int_and_str(self):
        def g(x: float) -> float:
            return x

        bound = bind_params_to_func(g, {'x': 2})
        self.assertEqual(g(*bound.args, **bound.kwargs), 2.0)

        bound = bind_params_to_func(g, {'x': ' 3.5 '})
        self.assertEqual(g(*bound.args, **bound.kwargs), 3.5)

    def test_str_from_non_str(self):
        def h(s: str) -> str:
            return s

        bound = bind_params_to_func(h, {'s': 123})
        self.assertEqual(h(*bound.args, **bound.kwargs), '123')

    def test_bool_variants_and_invalid(self):
        def b(flag: bool) -> bool:
            return flag

        for v in ['true', 'False', 'YES', 'no', '1', '0', 'on', 'off']:
            bound = bind_params_to_func(b, {'flag': v})
            # Ensure conversion yields actual bool
            self.assertIsInstance(b(*bound.args, **bound.kwargs), bool)

        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(b, {'flag': 'maybe'})


class TestEnumCoercions(unittest.TestCase):
    def test_enum_by_value_and_name_and_case_insensitive(self):
        def f(m: Mode) -> Mode:
            return m

        # by value
        bound = bind_params_to_func(f, {'m': 'red'})
        self.assertEqual(f(*bound.args, **bound.kwargs), Mode.RED)

        # by exact name
        bound = bind_params_to_func(f, {'m': 'BLUE'})
        self.assertEqual(f(*bound.args, **bound.kwargs), Mode.BLUE)

        # by case-insensitive name
        bound = bind_params_to_func(f, {'m': 'red'})  # value already tested; use name lower
        self.assertEqual(f(*bound.args, **bound.kwargs), Mode.RED)

        # invalid
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'m': 'green'})


class TestCoerceAndValidateBranches(unittest.TestCase):
    def test_optional_and_union(self):
        def f(a: Optional[int], b: Union[str, int]) -> tuple:
            return a, b

        bound = bind_params_to_func(f, {'a': '2', 'b': 5})
        # Union[str, int] tries str first; 5 is coerced to '5'
        self.assertEqual(f(*bound.args, **bound.kwargs), (2, '5'))

        bound = bind_params_to_func(f, {'a': None, 'b': 'hello'})
        self.assertEqual(f(*bound.args, **bound.kwargs), (None, 'hello'))

    def test_list_and_dict_coercion(self):
        def g(xs: List[int], mapping: Dict[int, float]) -> tuple:
            return xs, mapping

        bound = bind_params_to_func(g, {'xs': ['1', '2', '3'], 'mapping': {'1': '2.5', 3: 4}})
        xs, mapping = g(*bound.args, **bound.kwargs)
        self.assertEqual(xs, [1, 2, 3])
        self.assertEqual(mapping, {1: 2.5, 3: 4.0})

        # Wrong type for list
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(g, {'xs': 'not-a-list', 'mapping': {}})

        # Wrong type for dict
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(g, {'xs': [1], 'mapping': 'not-a-dict'})

    def test_dataclass_optional_and_rejection_of_dict(self):
        def f(p: Optional[DC]) -> Optional[str]:
            return None if p is None else p.y

        inst = DC(1, 'ok')
        bound = bind_params_to_func(f, {'p': inst})
        self.assertEqual(f(*bound.args, **bound.kwargs), 'ok')

        bound = bind_params_to_func(f, {'p': None})
        self.assertIsNone(f(*bound.args, **bound.kwargs))

        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'p': {'x': 1, 'y': 'no'}})

    def test_plain_class_construction_from_dict_and_missing_arg(self):
        def f(p: Plain) -> int:
            return p.a

        # Construct from dict with coercion
        bound = bind_params_to_func(f, {'p': {'a': '3'}})
        res = f(*bound.args, **bound.kwargs)
        self.assertEqual(res, 3)
        self.assertIsInstance(bound.arguments['p'], Plain)
        self.assertEqual(bound.arguments['p'].b, 'x')  # default applied

        # Missing required arg
        with self.assertRaises(ToolArgumentError):
            bind_params_to_func(f, {'p': {}})

    def test_any_and_isinstance_fallback(self):
        class C:
            ...

        def f(a: Any, c: C) -> tuple:
            return a, c

        c = C()
        with self.assertRaises(ToolArgumentError) as ctx:
            bind_params_to_func(f, {'a': object(), 'c': c})
        # _coerce_and_validate raises TypeError for Any; bind wraps it in ToolArgumentError
        self.assertIsInstance(ctx.exception.__cause__, TypeError)


# ---- Helpers for test stringify


class Shade(Enum):
    LIGHT = 'light'
    DARK = 'dark'


@dataclass
class Pair:
    a: int
    b: str


class PlainWithDict:
    def __init__(self):
        self.x = 10
        self.y = 'y'
        self.fn = lambda: 1  # callable should be filtered out


class TestStringifyToolOutputMore(unittest.TestCase):
    def test_bytes_and_bytearray_branch(self):
        raw = bytes([1, 2, 3, 254, 255])
        expected = 'base64:' + base64.b64encode(raw).decode('ascii')
        self.assertEqual(stringify_tool_output(raw), expected)

        ba = bytearray(raw)
        expected_ba = 'base64:' + base64.b64encode(bytes(ba)).decode('ascii')
        self.assertEqual(stringify_tool_output(ba), expected_ba)

    def test_default_encoder_enum_dataclass_and___dict__(self):
        # Enum -> value via default encoder (JSON string)
        out_enum = stringify_tool_output(Shade.DARK)
        self.assertEqual(out_enum, json.dumps('dark', ensure_ascii=False))

        # Dataclass -> asdict via default encoder
        p = Pair(3, 'z')
        out_dc = stringify_tool_output(p)
        self.assertEqual(json.loads(out_dc), {'a': 3, 'b': 'z'})

        # __dict__ plain object -> filtered dict via default encoder
        obj = PlainWithDict()
        out_obj = stringify_tool_output(obj)
        self.assertEqual(json.loads(out_obj), {'x': 10, 'y': 'y'})


if __name__ == '__main__':
    unittest.main()
