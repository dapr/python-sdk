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
from unittest.mock import patch

from dapr.clients import analytics


class AnalyticsOptOutTests(unittest.TestCase):
    def setUp(self):
        analytics._reported = False

    def test_enabled_when_no_opt_out_set(self):
        with patch.dict('os.environ', {name: '' for name in analytics.OPT_OUT_ENV_VARS}):
            self.assertFalse(analytics.analytics_disabled())

    def test_each_opt_out_variable_disables(self):
        for name in analytics.OPT_OUT_ENV_VARS:
            env = {other: '' for other in analytics.OPT_OUT_ENV_VARS}
            env[name] = '1'
            with self.subTest(variable=name):
                with patch.dict('os.environ', env):
                    self.assertTrue(analytics.analytics_disabled())

    def test_falsy_values_do_not_disable(self):
        for value in ('0', 'false', 'no', 'off', ''):
            env = {other: '' for other in analytics.OPT_OUT_ENV_VARS}
            env['DO_NOT_TRACK'] = value
            with self.subTest(value=value):
                with patch.dict('os.environ', env):
                    self.assertFalse(analytics.analytics_disabled())

    def test_truthy_values_are_case_and_space_insensitive(self):
        for value in ('1', 'TRUE', ' yes ', 'On'):
            env = {other: '' for other in analytics.OPT_OUT_ENV_VARS}
            env['DO_NOT_TRACK'] = value
            with self.subTest(value=value):
                with patch.dict('os.environ', env):
                    self.assertTrue(analytics.analytics_disabled())


class AnalyticsReportingTests(unittest.TestCase):
    def setUp(self):
        analytics._reported = False

    def test_no_event_sent_when_opted_out(self):
        with patch.dict('os.environ', {'DO_NOT_TRACK': '1'}):
            with patch.object(analytics.threading, 'Thread') as thread:
                analytics.report_analytics()
                thread.assert_not_called()

    def test_event_sent_once_per_process(self):
        env = {name: '' for name in analytics.OPT_OUT_ENV_VARS}
        with patch.dict('os.environ', env):
            with patch.object(analytics.threading, 'Thread') as thread:
                analytics.report_analytics()
                analytics.report_analytics()
                analytics.report_analytics()
                self.assertEqual(thread.call_count, 1)

    def test_send_failure_is_swallowed(self):
        with patch.object(
            analytics.urllib.request, 'urlopen', side_effect=OSError('network unreachable')
        ):
            # Must not raise — blocked egress is a normal condition.
            analytics._send_event()

    def test_report_never_raises(self):
        with patch.object(analytics, 'analytics_disabled', side_effect=RuntimeError('boom')):
            analytics.report_analytics()

    def test_url_contains_expected_dimensions(self):
        url = analytics._build_url()
        self.assertTrue(url.startswith(analytics.ANALYTICS_ENDPOINT))
        for key in ('version', 'os', 'arch', 'python_version'):
            self.assertIn(f'{key}=', url)


if __name__ == '__main__':
    unittest.main()
