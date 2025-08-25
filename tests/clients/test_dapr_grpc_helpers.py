import base64
import unittest

from google.protobuf.struct_pb2 import Struct
from google.protobuf import json_format
from google.protobuf.json_format import ParseError
from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.wrappers_pb2 import (
    BoolValue,
    StringValue,
    Int32Value,
    Int64Value,
    DoubleValue,
    BytesValue,
)

from dapr.clients.grpc._helpers import (
    convert_value_to_struct,
    convert_dict_to_grpc_dict_of_any,
)


class TestConvertValueToStruct(unittest.TestCase):
    def test_struct_passthrough_same_instance(self):
        # Prepare a Struct
        original = Struct()
        json_format.ParseDict({"a": 1, "b": "x"}, original)

        # It should return the exact same instance
        result = convert_value_to_struct(original)
        self.assertIs(result, original)

    def test_simple_and_nested_dict_conversion(self):
        payload = {
            "a": "b",
            "n": 3,
            "t": True,
            "f": 1.5,
            "none": None,
            "list": [1, "x", False, None],
            "obj": {"k": "v", "inner": {"i": 2, "j": None}},
        }
        struct = convert_value_to_struct(payload)

        # Convert back to dict to assert equivalence
        back = json_format.MessageToDict(struct, preserving_proto_field_name=True)
        self.assertEqual(back, {
            "a": "b",
            "n": 3,
            "t": True,
            "f": 1.5,
            "none": None,
            "list": [1, "x", False, None],
            "obj": {"k": "v", "inner": {"i": 2, "j": None}},
        })

    def test_invalid_non_dict_non_bytes_types_raise(self):
        for bad in [
            "str",
            42,
            3.14,
            True,
            None,
            [1, 2, 3],
        ]:
            with self.subTest(value=bad):
                with self.assertRaises(ValueError) as ctx:
                    convert_value_to_struct(bad)  # type: ignore[arg-type]
                self.assertIn("Value must be a dictionary, got", str(ctx.exception))

    def test_bytes_input_raises_parse_error(self):
        data = b"hello world"
        # The implementation base64-encodes bytes then attempts to ParseDict a string,
        # which results in a ParseError from protobuf's json_format.
        with self.assertRaises(ParseError) as ctx:
            convert_value_to_struct(data)
        msg = str(ctx.exception)
        # Ensure the base64 string is what would have been produced (implementation detail)
        expected_b64 = base64.b64encode(data).decode("utf-8")
        self.assertIn(expected_b64, msg)

    def test_dict_with_non_string_key_raises_wrapped_value_error(self):
        # Struct JSON object keys must be strings; non-string key should cause parse error
        bad_dict = {1: "a", "ok": 2}  # type: ignore[dict-item]
        with self.assertRaises(ValueError) as ctx:
            convert_value_to_struct(bad_dict)  # type: ignore[arg-type]
        self.assertIn("Unsupported parameter type or value", str(ctx.exception))

    def test_json_roundtrip_struct_to_dict_to_json(self):
        import json

        # Start with a JSON string (could come from any external source)
        original_json = json.dumps({
            "a": "b",
            "n": 3,
            "t": True,
            "f": 1.5,
            "none": None,
            "list": [1, "x", False, None],
            "obj": {"k": "v", "inner": {"i": 2, "j": None}},
        })

        # JSON -> dict
        original_dict = json.loads(original_json)

        # dict -> Struct
        struct = convert_value_to_struct(original_dict)

        # Struct -> dict
        back_to_dict = json_format.MessageToDict(struct, preserving_proto_field_name=True)

        # dict -> JSON
        final_json = json.dumps(back_to_dict, separators=(",", ":"), sort_keys=True)

        # Validate: parsing final_json should yield the original_dict structure
        # Note: We compare dicts to avoid key-order issues and formatting differences
        self.assertEqual(json.loads(final_json), original_dict)


class TestConvertDictToGrpcDictOfAny(unittest.TestCase):
    def test_none_and_empty_return_empty_dict(self):
        self.assertEqual(convert_dict_to_grpc_dict_of_any(None), {})
        self.assertEqual(convert_dict_to_grpc_dict_of_any({}), {})

    def test_basic_types_conversion(self):
        params = {
            "s": "hello",
            "b": True,
            "i32": 123,
            "i64": 2**40,
            "f": 3.14,
            "bytes": b"abc",
        }
        result = convert_dict_to_grpc_dict_of_any(params)

        # Ensure all keys present
        self.assertEqual(set(result.keys()), set(params.keys()))

        # Check each Any contains the proper wrapper with correct value
        sv = StringValue()
        self.assertTrue(result["s"].Unpack(sv))
        self.assertEqual(sv.value, "hello")

        bv = BoolValue()
        self.assertTrue(result["b"].Unpack(bv))
        self.assertEqual(bv.value, True)

        i32v = Int32Value()
        self.assertTrue(result["i32"].Unpack(i32v))
        self.assertEqual(i32v.value, 123)

        i64v = Int64Value()
        self.assertTrue(result["i64"].Unpack(i64v))
        self.assertEqual(i64v.value, 2**40)

        dv = DoubleValue()
        self.assertTrue(result["f"].Unpack(dv))
        self.assertAlmostEqual(dv.value, 3.14)

        byv = BytesValue()
        self.assertTrue(result["bytes"].Unpack(byv))
        self.assertEqual(byv.value, b"abc")

    def test_pass_through_existing_any_instances(self):
        # Prepare Any values
        any_s = GrpcAny()
        any_s.Pack(StringValue(value="x"))
        any_i = GrpcAny()
        any_i.Pack(Int64Value(value=9999999999))

        params = {"s": any_s, "i": any_i}
        result = convert_dict_to_grpc_dict_of_any(params)

        # Should be the exact same Any instances
        self.assertIs(result["s"], any_s)
        self.assertIs(result["i"], any_i)

    def test_unsupported_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            convert_dict_to_grpc_dict_of_any({"bad": [1, 2, 3]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
