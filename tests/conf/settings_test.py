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

import os
import unittest
from unittest import mock

from dapr.actor.client.proxy import ActorProxyFactory
from dapr.actor.runtime.grpc_host import ActorGrpcHost
from dapr.clients.grpc._channel import resolve_grpc_endpoint
from dapr.clients.retry import RetryPolicy
from dapr.conf import Settings, global_settings, settings


class SettingsReadEnvAtAccessTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        names = (
            'DAPR_GRPC_ENDPOINT',
            'DAPR_GRPC_PORT',
            'DAPR_API_MAX_RETRIES',
            'DAPR_HTTP_ENDPOINT',
            'DAPR_HTTP_TIMEOUT_SECONDS',
        )
        for name in names:
            os.environ.pop(name, None)
            # Other tests assign on the shared instance; drop those so env is visible.
            settings.__dict__.pop(name, None)

    def test_env_set_after_import_is_seen(self):
        self.assertIsNone(settings.DAPR_GRPC_ENDPOINT)

        os.environ['DAPR_GRPC_ENDPOINT'] = 'grpc-example.example.com:443'

        self.assertEqual('grpc-example.example.com:443', settings.DAPR_GRPC_ENDPOINT)

    def test_env_change_and_removal_is_seen(self):
        os.environ['DAPR_GRPC_PORT'] = '1234'
        self.assertEqual(1234, settings.DAPR_GRPC_PORT)

        os.environ['DAPR_GRPC_PORT'] = '5678'
        self.assertEqual(5678, settings.DAPR_GRPC_PORT)

        del os.environ['DAPR_GRPC_PORT']
        self.assertEqual(global_settings.DAPR_GRPC_PORT, settings.DAPR_GRPC_PORT)

    def test_empty_env_uses_default(self):
        os.environ['DAPR_GRPC_PORT'] = ''
        self.assertEqual(global_settings.DAPR_GRPC_PORT, settings.DAPR_GRPC_PORT)

    def test_explicit_assignment_wins_over_env(self):
        local = Settings()
        os.environ['DAPR_GRPC_PORT'] = '1234'
        local.DAPR_GRPC_PORT = 4321

        self.assertEqual(4321, local.DAPR_GRPC_PORT)
        os.environ['DAPR_GRPC_PORT'] = '9999'
        self.assertEqual(4321, local.DAPR_GRPC_PORT)

        del local.DAPR_GRPC_PORT
        self.assertEqual(9999, local.DAPR_GRPC_PORT)

    def test_unknown_setting_raises(self):
        with self.assertRaises(AttributeError):
            settings.DAPR_DOES_NOT_EXIST  # noqa: B018

    def test_grpc_endpoint_resolution_uses_env_set_after_import(self):
        os.environ['DAPR_GRPC_ENDPOINT'] = 'grpc-example.example.com:443'

        self.assertEqual(
            'dns:grpc-example.example.com:443',
            resolve_grpc_endpoint(None).endpoint,
        )

    def test_retry_policy_default_reads_env_at_construction(self):
        os.environ['DAPR_API_MAX_RETRIES'] = '7'

        self.assertEqual(7, RetryPolicy().max_attempts)
        self.assertEqual(3, RetryPolicy(max_attempts=3).max_attempts)

    def test_retry_policy_zero_from_env(self):
        os.environ['DAPR_API_MAX_RETRIES'] = '0'
        self.assertEqual(0, RetryPolicy().max_attempts)

    def test_invalid_env_value_names_the_setting(self):
        os.environ['DAPR_GRPC_PORT'] = 'abc'
        with self.assertRaisesRegex(ValueError, 'DAPR_GRPC_PORT'):
            settings.DAPR_GRPC_PORT  # noqa: B018

    def test_dir_lists_settings(self):
        self.assertIn('DAPR_GRPC_ENDPOINT', dir(settings))

    def test_http_endpoint_from_env(self):
        os.environ['DAPR_HTTP_ENDPOINT'] = 'http://example.com:3500'
        self.assertEqual('http://example.com:3500', settings.DAPR_HTTP_ENDPOINT)

    def test_actor_timeout_defaults_read_env_at_call(self):
        os.environ['DAPR_HTTP_TIMEOUT_SECONDS'] = '7'
        with mock.patch('dapr.actor.client.proxy.DaprActorHttpClient') as client:
            ActorProxyFactory()
        self.assertEqual(7, client.call_args.kwargs['timeout'])
        self.assertEqual(7, ActorGrpcHost(app_port=0)._timeout_seconds)
        self.assertEqual(3, ActorGrpcHost(timeout_seconds=3, app_port=0)._timeout_seconds)


if __name__ == '__main__':
    unittest.main()
