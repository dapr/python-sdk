import base64
import unittest

from google.protobuf.struct_pb2 import Struct
from google.protobuf import json_format
from google.protobuf.json_format import ParseError

from dapr.clients.grpc._helpers import convert_value_to_struct


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
