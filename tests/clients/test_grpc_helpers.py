#!/usr/bin/env python3

"""
Tests for gRPC helper functions, particularly parameter conversion.

This test suite covers the parameter conversion functionality that improves
developer experience by automatically converting raw Python values to
protobuf Any objects for the conversation API.
"""

import unittest

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.wrappers_pb2 import BoolValue, DoubleValue, Int32Value, Int64Value, StringValue

from dapr.clients.grpc._helpers import convert_parameters_for_grpc


class GrpcHelpersTests(unittest.TestCase):
    """Tests for gRPC helper functions."""

    def test_convert_parameters_empty(self):
        """Test conversion of empty parameters."""
        result = convert_parameters_for_grpc(None)
        self.assertEqual(result, {})

        result = convert_parameters_for_grpc({})
        self.assertEqual(result, {})

    def test_convert_parameters_string(self):
        """Test conversion of string parameters."""
        params = {"tool_choice": "auto", "model": "gpt-4"}
        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result["tool_choice"], GrpcAny)
        self.assertIsInstance(result["model"], GrpcAny)

        # Verify the string values can be unpacked correctly
        string_value = StringValue()
        result["tool_choice"].Unpack(string_value)
        self.assertEqual(string_value.value, "auto")

        result["model"].Unpack(string_value)
        self.assertEqual(string_value.value, "gpt-4")

    def test_convert_parameters_bool(self):
        """Test conversion of boolean parameters."""
        params = {"stream": True, "echo": False}
        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 2)

        # Verify boolean values
        bool_value = BoolValue()
        result["stream"].Unpack(bool_value)
        self.assertTrue(bool_value.value)

        result["echo"].Unpack(bool_value)
        self.assertFalse(bool_value.value)

    def test_convert_parameters_int(self):
        """Test conversion of integer parameters."""
        params = {
            "max_tokens": 1000,
            "small_int": 42,
            "large_int": 9999999999,  # Larger than Int32 range
            "negative_int": -500
        }
        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 4)

        # Test Int32 values
        int32_value = Int32Value()
        result["max_tokens"].Unpack(int32_value)
        self.assertEqual(int32_value.value, 1000)

        result["small_int"].Unpack(int32_value)
        self.assertEqual(int32_value.value, 42)

        result["negative_int"].Unpack(int32_value)
        self.assertEqual(int32_value.value, -500)

        # Test Int64 value (large integer)
        int64_value = Int64Value()
        result["large_int"].Unpack(int64_value)
        self.assertEqual(int64_value.value, 9999999999)

    def test_convert_parameters_float(self):
        """Test conversion of float parameters."""
        params = {
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": -1.5,
            "presence_penalty": 2.0
        }
        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 4)

        # Verify float values
        double_value = DoubleValue()
        result["temperature"].Unpack(double_value)
        self.assertAlmostEqual(double_value.value, 0.7, places=6)

        result["top_p"].Unpack(double_value)
        self.assertAlmostEqual(double_value.value, 0.9, places=6)

        result["frequency_penalty"].Unpack(double_value)
        self.assertAlmostEqual(double_value.value, -1.5, places=6)

    def test_convert_parameters_mixed_types(self):
        """Test conversion of mixed parameter types."""
        params = {
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": False,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }
        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 7)

        # Verify all parameters are GrpcAny objects
        for key, value in result.items():
            self.assertIsInstance(value, GrpcAny, f"Parameter {key} is not a GrpcAny object")

    def test_convert_parameters_backward_compatibility(self):
        """Test that pre-wrapped protobuf Any objects are preserved."""
        # Create a pre-wrapped parameter
        pre_wrapped_any = GrpcAny()
        pre_wrapped_any.Pack(StringValue(value="manual"))

        params = {
            "tool_choice": "auto",  # Raw string
            "manual_param": pre_wrapped_any,  # Pre-wrapped
            "temperature": 0.8,  # Raw float
        }

        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 3)

        # Verify pre-wrapped parameter is unchanged (same object reference)
        self.assertIs(result["manual_param"], pre_wrapped_any)

        # Verify other parameters are converted
        self.assertIsInstance(result["tool_choice"], GrpcAny)
        self.assertIsInstance(result["temperature"], GrpcAny)

        # Verify the pre-wrapped value is still correct
        string_value = StringValue()
        result["manual_param"].Unpack(string_value)
        self.assertEqual(string_value.value, "manual")

    def test_convert_parameters_unsupported_types(self):
        """Test conversion of unsupported types (should convert to string)."""
        params = {
            "list_param": ["item1", "item2"],
            "dict_param": {"key": "value"},
            "none_param": None,
            "complex_param": complex(1, 2)
        }
        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 4)

        # All should be converted to strings
        string_value = StringValue()

        result["list_param"].Unpack(string_value)
        self.assertEqual(string_value.value, "['item1', 'item2']")

        result["dict_param"].Unpack(string_value)
        self.assertEqual(string_value.value, "{'key': 'value'}")

        result["none_param"].Unpack(string_value)
        self.assertEqual(string_value.value, "None")

        result["complex_param"].Unpack(string_value)
        self.assertEqual(string_value.value, "(1+2j)")

    def test_convert_parameters_edge_cases(self):
        """Test edge cases for parameter conversion."""
        # Test integer boundary values
        params = {
            "int32_min": -2147483648,  # Int32 minimum
            "int32_max": 2147483647,   # Int32 maximum
            "int64_min": -2147483649,  # Just below Int32 minimum
            "int64_max": 2147483648,   # Just above Int32 maximum
        }
        result = convert_parameters_for_grpc(params)

        # Verify Int32 boundary values use Int32Value
        int32_value = Int32Value()
        result["int32_min"].Unpack(int32_value)
        self.assertEqual(int32_value.value, -2147483648)

        result["int32_max"].Unpack(int32_value)
        self.assertEqual(int32_value.value, 2147483647)

        # Verify values outside Int32 range use Int64Value
        int64_value = Int64Value()
        result["int64_min"].Unpack(int64_value)
        self.assertEqual(int64_value.value, -2147483649)

        result["int64_max"].Unpack(int64_value)
        self.assertEqual(int64_value.value, 2147483648)

    def test_convert_parameters_bool_priority(self):
        """Test that bool is checked before int (since bool is subclass of int)."""
        params = {"flag": True}
        result = convert_parameters_for_grpc(params)

        # Should be BoolValue, not Int32Value
        bool_value = BoolValue()
        result["flag"].Unpack(bool_value)
        self.assertTrue(bool_value.value)

        # Verify it's actually a BoolValue by checking the type_url
        self.assertTrue(result["flag"].type_url.endswith('BoolValue'))

    def test_convert_parameters_realistic_openai_example(self):
        """Test with realistic OpenAI-style parameters."""
        params = {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "stream": False,
            "tool_choice": "auto",
            "response_format": {"type": "text"}  # Will be converted to string
        }

        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 9)

        # Verify specific values
        string_value = StringValue()
        result["model"].Unpack(string_value)
        self.assertEqual(string_value.value, "gpt-4o-mini")

        double_value = DoubleValue()
        result["temperature"].Unpack(double_value)
        self.assertAlmostEqual(double_value.value, 0.7, places=6)

        int32_value = Int32Value()
        result["max_tokens"].Unpack(int32_value)
        self.assertEqual(int32_value.value, 1000)

        bool_value = BoolValue()
        result["stream"].Unpack(bool_value)
        self.assertFalse(bool_value.value)

    def test_convert_parameters_realistic_anthropic_example(self):
        """Test with realistic Anthropic-style parameters."""
        params = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "temperature": 0.8,
            "top_p": 0.9,
            "top_k": 250,
            "stream": True,
            "tool_choice": {"type": "auto"}  # Will be converted to string
        }

        result = convert_parameters_for_grpc(params)

        self.assertEqual(len(result), 7)

        # All should be properly converted
        for key, value in result.items():
            self.assertIsInstance(value, GrpcAny, f"Parameter {key} is not converted")


if __name__ == '__main__':
    unittest.main()
