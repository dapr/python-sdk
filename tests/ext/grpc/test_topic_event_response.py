# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from dapr.clients.grpc._response import TopicEventResponse, TopicEventResponseStatus


class TopicEventResponseTests(unittest.TestCase):
    def test_topic_event_response_creation_from_enum(self):
        for status in TopicEventResponseStatus:
            response = TopicEventResponse(status)
            self.assertEqual(response.status.value, status.value)

    def test_topic_event_response_creation_fails(self):
        with self.assertRaises(KeyError):
            TopicEventResponse('invalid')

    def test_topic_event_response_creation_from_str(self):
        for status in TopicEventResponseStatus:
            response = TopicEventResponse(status.name)
            self.assertEqual(response.status.value, status.value)

    def test_topic_event_response_creation_fails_with_object(self):
        with self.assertRaises(ValueError):
            TopicEventResponse(None)


if __name__ == '__main__':
    unittest.main()
