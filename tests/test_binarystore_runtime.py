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

import subprocess
import unittest
from unittest.mock import patch

import pytest

from tests.binarystore_utils import require_binary_store_runtime


class BinaryStoreRuntimeGateTests(unittest.TestCase):
    @patch.dict('os.environ', {'DAPR_TEST_REQUIRE_BINARY_STORE': '1'})
    @patch('tests.binarystore_utils.subprocess.run')
    def test_capable_selected_runtime(self, run):
        for version in [
            '1.19.0-rc.3',
            '1.19.0-rc.4',
            '1.19.0',
            '1.19.1',
            '1.20.0',
            'v1.19.0',
            '1.19.0+local',
            '1.19.0-rc.3+sha',
        ]:
            with self.subTest(version=version):
                run.return_value.stdout = f'CLI version: 1.18.2\nRuntime version: {version}\n'
                require_binary_store_runtime()

    @patch.dict('os.environ', {'DAPR_TEST_REQUIRE_BINARY_STORE': ''})
    @patch('tests.binarystore_utils.subprocess.run')
    def test_older_or_unknown_runtime_skips_before_component_loading(self, run):
        for version in ['n/a', '1.18.0', '1.19.0-rc.1', '1.19.0-rc.2', '1.19.0-rc.2+sha']:
            with self.subTest(version=version), self.assertRaises(pytest.skip.Exception):
                run.return_value.stdout = f'Runtime version: {version}'
                require_binary_store_runtime()

    @patch.dict('os.environ', {'DAPR_TEST_REQUIRE_BINARY_STORE': '1'})
    @patch('tests.binarystore_utils.subprocess.run')
    def test_strict_job_fails_on_missing_or_incompatible_runtime(self, run):
        run.return_value.stdout = 'Runtime version: 1.18.0'
        with self.assertRaises(pytest.fail.Exception):
            require_binary_store_runtime()
        for failure in [FileNotFoundError(), subprocess.TimeoutExpired('dapr', 15)]:
            with self.subTest(failure=failure), self.assertRaises(pytest.fail.Exception):
                run.side_effect = failure
                require_binary_store_runtime()
