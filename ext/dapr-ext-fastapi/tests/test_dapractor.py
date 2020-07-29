# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import json
import unittest

from dapr.ext.fastapi.actor import _wrap_response


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


if __name__ == '__main__':
    unittest.main()
