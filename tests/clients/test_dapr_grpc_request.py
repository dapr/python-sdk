# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

import unittest

from dapr.clients.grpc._request import InvokeMethodRequest, BindingRequest
from dapr.proto import common_v1


class InvokeMethodRequestTests(unittest.TestCase):
    def test_bytes_data(self):
        # act
        req = InvokeMethodRequest(data=b"hello dapr")

        # arrange
        self.assertEqual(b"hello dapr", req.data)
        self.assertEqual("application/json; charset=utf-8", req.content_type)

    def test_proto_message_data(self):
        # arrange
        fake_req = common_v1.InvokeRequest(method="test")

        # act
        req = InvokeMethodRequest(data=fake_req)

        # assert
        self.assertIsNotNone(req.proto)
        self.assertEqual(
            "type.googleapis.com/dapr.proto.common.v1.InvokeRequest", req.proto.type_url
        )
        self.assertIsNotNone(req.proto.value)
        self.assertIsNone(req.content_type)

    def test_invalid_data(self):
        with self.assertRaises(ValueError):
            data = InvokeMethodRequest(data=123)
            self.assertIsNone(data, "This should not be reached.")


class InvokeBindingRequestDataTests(unittest.TestCase):
    def test_bytes_data(self):
        # act
        data = BindingRequest(data=b"hello dapr")

        # arrange
        self.assertEqual(b"hello dapr", data.data)
        self.assertEqual({}, data.metadata)

    def test_str_data(self):
        # act
        data = BindingRequest(data="hello dapr")

        # arrange
        self.assertEqual(b"hello dapr", data.data)
        self.assertEqual({}, data.metadata)

    def test_non_empty_metadata(self):
        # act
        data = BindingRequest(data="hello dapr", binding_metadata={"ttlInSeconds": "1000"})

        # arrange
        self.assertEqual(b"hello dapr", data.data)
        self.assertEqual({"ttlInSeconds": "1000"}, data.binding_metadata)


if __name__ == "__main__":
    unittest.main()
