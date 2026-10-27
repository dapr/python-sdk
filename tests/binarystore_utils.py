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

import io
import os
import re
import subprocess
import threading

import pytest


def require_binary_store_runtime() -> None:
    """Gate before sidecar startup; the dedicated feature job must never skip."""
    reason = 'Binary store requires Dapr runtime 1.19.0-rc.3 or later'
    try:
        result = subprocess.run(
            ['dapr', '--version'], capture_output=True, text=True, timeout=15, check=True
        )
        match = re.search(r'Runtime version:\s*v?(\d+)\.(\d+)\.(\d+)([^\s]*)', result.stdout)
        if match:
            version = tuple(int(part) for part in match.group(1, 2, 3))
            # Build metadata does not change version precedence (for example,
            # a locally built 1.19.0+sha runtime still contains the API).
            suffix = match.group(4).split('+', 1)[0]
            rc = re.fullmatch(r'-rc\.(\d+)', suffix)
            if version > (1, 19, 0) or (
                version == (1, 19, 0) and (not suffix or (rc and int(rc[1]) >= 3))
            ):
                return
        reason += f'; selected CLI reports: {result.stdout.strip()}'
    except (OSError, subprocess.SubprocessError) as error:
        reason += f'; runtime probe failed: {error}'
    if os.environ.get('DAPR_TEST_REQUIRE_BINARY_STORE') == '1':
        pytest.fail(reason)
    pytest.skip(reason)


class EndOfUploadReader(io.BytesIO):
    """Hold EOF so tests can inspect a component before the upload can commit."""

    def __init__(self, data: bytes):
        super().__init__(data)
        self.ready = threading.Event()
        self.release = threading.Event()

    def read(self, size: int = -1) -> bytes:
        chunk = super().read(size)
        if not chunk:
            self.ready.set()
            if not self.release.wait(10):
                raise TimeoutError('test did not release the upload EOF gate')
        return chunk
