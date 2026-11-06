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

import pytest

from tests.binarystore_utils import require_binary_store_runtime

pytestmark = [pytest.mark.binary_store, pytest.mark.example_dir('binary-store')]


@pytest.mark.parametrize('script', ['binary_store.py', 'binary_store_async.py'])
def test_binary_store(dapr, script):
    require_binary_store_runtime()
    output = dapr.run(
        f'--app-id binary-store-example --resources-path ./components -- python3 {script}',
        timeout=45,
    )
    for line in [
        'Binary file round trip: 262144 bytes',
        'Overwritten file: replaced',
        'Binary file deleted',
    ]:
        assert line in output, f'Missing in output: {line}'
