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

EXPECTED_ACTOR_PATHS = {
    '/healthz',
    '/dapr/config',
    '/actors/{actor_type_name}/{actor_id}',
    '/actors/{actor_type_name}/{actor_id}/method/{method_name}',
    '/actors/{actor_type_name}/{actor_id}/method/timer/{timer_name}',
    '/actors/{actor_type_name}/{actor_id}/method/remind/{reminder_name}',
}


def _operation_tags(app: FastAPI) -> list[tuple[str, list[str] | None]]:
    """Returns the ``(path, tags)`` pair of every operation in the app's OpenAPI schema.

    The schema is read instead of ``app.router.routes`` because FastAPI 0.137+ stores
    routes registered via ``include_router`` in a nested tree rather than a flat list, so
    the actor routes no longer surface as top-level ``APIRoute`` objects. The OpenAPI
    schema is the public, stable surface that ``router_tags`` is meant to drive.
    """
    schema = app.openapi()
    return [
        (path, operation.get('tags'))
        for path, operations in schema['paths'].items()
        for operation in operations.values()
    ]


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

        custom_tag_operations = _operation_tags(app1)
        self.assertEqual(EXPECTED_ACTOR_PATHS, {path for path, _tags in custom_tag_operations})
        for _path, tags in custom_tag_operations:
            self.assertEqual(['MyTag', 'Actor'], tags)

        default_tag_operations = _operation_tags(app2)
        self.assertEqual(EXPECTED_ACTOR_PATHS, {path for path, _tags in default_tag_operations})
        for _path, tags in default_tag_operations:
            self.assertEqual(['Actor'], tags)

        untagged_operations = _operation_tags(app3)
        self.assertEqual(EXPECTED_ACTOR_PATHS, {path for path, _tags in untagged_operations})
        for _path, tags in untagged_operations:
            self.assertFalse(tags)


if __name__ == '__main__':
    unittest.main()
