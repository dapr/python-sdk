# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest
from tests.process_utils import get_kwargs_for_process_group, terminate_process_group

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / 'examples'
MCP_DIR = EXAMPLES_DIR / 'mcp'

# Lines we expect the example to print during a successful run. We don't pin
# tool names or counts beyond what the bundled weather server produces, so the
# checks survive small wording tweaks to the example script.
EXPECTED_LINES = [
    "Connecting to MCPServer 'weather'",
    'Discovered ',
    'Name:        get_weather',
    'Workflow:    dapr.internal.mcp.weather.CallTool.get_weather',
    'Status: COMPLETED',
]


@pytest.fixture
def weather_mcp_server() -> Generator[subprocess.Popen, None, None]:
    """Start the bundled weather MCP server on :8081 for the duration of the test."""
    proc = subprocess.Popen(
        args=(sys.executable, str(MCP_DIR / 'weather_mcp_server.py')),
        cwd=MCP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **get_kwargs_for_process_group(),
    )
    # Give the server a moment to bind :8081 before the example tries to connect.
    time.sleep(3)
    if proc.poll() is not None:
        out = proc.stdout.read() if proc.stdout else ''
        pytest.fail(f'weather_mcp_server.py exited early:\n{out}')
    try:
        yield proc
    finally:
        terminate_process_group(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            terminate_process_group(proc, force=True)
            proc.wait()


@pytest.mark.example_dir('mcp')
def test_mcp_tool_discovery(dapr, weather_mcp_server):
    output = dapr.run(
        '--app-id mcp-demo --resources-path ./resources -- python3 mcp_tool_discovery.py',
        timeout=60,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
