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

import json
import unittest

from fastapi import FastAPI

from dapr.ext.fastapi.actor import DaprActor, _wrap_response


class DaprActorTest(unittest.TestCase):
    def test_wrap_response_str(self):
        r = _wrap_response(200, 'fake_message')
        self.assertEqual({'message': 'fake_message'}, json.loads(r.body))
        self.assertEqual(200, r.status_code)

    def test_wrap_response_str_err(self):
        r = _wrap_response(400, 'fake_message', 'ERR_FAKE')
        self.assertEqual({'message': 'fake_message', 'errorCode': 'ERR_FAKE'}, json.loads(r.body))
        self.assertEqual(400, r.status_code)

    def test_wrap_response_bytes_text(self):
        r = _wrap_response(200, b'fake_bytes_message', content_type='text/plain')
        self.assertEqual(b'fake_bytes_message', r.body)
        self.assertEqual(200, r.status_code)
        self.assertEqual('text/plain', r.media_type)

    def test_wrap_response_obj(self):
        fake_data = {'message': 'ok'}
        r = _wrap_response(200, fake_data)
        self.assertEqual(fake_data, json.loads(r.body))
        self.assertEqual(200, r.status_code)

    def test_router_tag(self):
        app1 = FastAPI()
        app2 = FastAPI()
        app3 = FastAPI()
        DaprActor(app=app1, router_tags=['MyTag', 'Actor'])
        DaprActor(app=app2)
        DaprActor(app=app3, router_tags=None)

        PATHS_WITH_EXPECTED_TAGS = [
            '/healthz',
            '/dapr/config',
            '/actors/{actor_type_name}/{actor_id}',
            '/actors/{actor_type_name}/{actor_id}/method/{method_name}',
            '/actors/{actor_type_name}/{actor_id}/method/timer/{timer_name}',
            '/actors/{actor_type_name}/{actor_id}/method/remind/{reminder_name}',
        ]

        foundTags = False
        for route in app1.router.routes:
            if hasattr(route, 'tags'):
                self.assertIn(route.path, PATHS_WITH_EXPECTED_TAGS)
                self.assertEqual(['MyTag', 'Actor'], route.tags)
                foundTags = True
        if not foundTags:
            self.fail('No tags found')

        foundTags = False
        for route in app2.router.routes:
            if hasattr(route, 'tags'):
                self.assertIn(route.path, PATHS_WITH_EXPECTED_TAGS)
                self.assertEqual(['Actor'], route.tags)
                foundTags = True
        if not foundTags:
            self.fail('No tags found')

        for route in app3.router.routes:
            if hasattr(route, 'tags'):
                if len(route.tags) > 0:
                    self.fail('Found tags on route that should not have any')


if __name__ == '__main__':
    unittest.main()
