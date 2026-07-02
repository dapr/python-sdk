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

import dapr as dapr_pkg

_ENV = dapr_pkg._GRPC_DNS_RESOLVER_ENV
_NATIVE = dapr_pkg._GRPC_DNS_RESOLVER_NATIVE


class TestDefaultGrpcDnsResolverNative(unittest.TestCase):
    def test_sets_native_on_darwin_when_unset(self):
        with (
            mock.patch.object(dapr_pkg.sys, 'platform', 'darwin'),
            mock.patch.dict(dapr_pkg.os.environ, {}, clear=True),
        ):
            dapr_pkg._default_grpc_dns_resolver_native()
            self.assertEqual(dapr_pkg.os.environ[_ENV], _NATIVE)

    def test_preserves_explicit_value_on_darwin(self):
        with (
            mock.patch.object(dapr_pkg.sys, 'platform', 'darwin'),
            mock.patch.dict(dapr_pkg.os.environ, {_ENV: 'ares'}, clear=True),
        ):
            dapr_pkg._default_grpc_dns_resolver_native()
            self.assertEqual(dapr_pkg.os.environ[_ENV], 'ares')

    def test_noop_on_non_darwin(self):
        with (
            mock.patch.object(dapr_pkg.sys, 'platform', 'linux'),
            mock.patch.dict(dapr_pkg.os.environ, {}, clear=True),
        ):
            dapr_pkg._default_grpc_dns_resolver_native()
            self.assertNotIn(_ENV, dapr_pkg.os.environ)


if __name__ == '__main__':
    unittest.main()
