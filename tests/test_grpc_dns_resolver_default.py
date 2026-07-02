# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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
from unittest import mock

from dapr.clients.grpc import _helpers

_ENV = _helpers._GRPC_DNS_RESOLVER_ENV
_NATIVE = _helpers._GRPC_DNS_RESOLVER_NATIVE


class TestSetDefaultGrpcDnsResolver(unittest.TestCase):
    def test_sets_native_on_darwin_when_unset(self):
        with (
            mock.patch.object(_helpers.sys, 'platform', 'darwin'),
            mock.patch.dict(_helpers.os.environ, {}, clear=True),
        ):
            _helpers.set_default_grpc_dns_resolver()
            self.assertEqual(_helpers.os.environ[_ENV], _NATIVE)

    def test_preserves_explicit_value_on_darwin(self):
        with (
            mock.patch.object(_helpers.sys, 'platform', 'darwin'),
            mock.patch.dict(_helpers.os.environ, {_ENV: 'ares'}, clear=True),
        ):
            _helpers.set_default_grpc_dns_resolver()
            self.assertEqual(_helpers.os.environ[_ENV], 'ares')

    def test_noop_on_non_darwin(self):
        with (
            mock.patch.object(_helpers.sys, 'platform', 'linux'),
            mock.patch.dict(_helpers.os.environ, {}, clear=True),
        ):
            _helpers.set_default_grpc_dns_resolver()
            self.assertNotIn(_ENV, _helpers.os.environ)


if __name__ == '__main__':
    unittest.main()
