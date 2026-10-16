# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

import socket
import unittest


def listen_without_replying(test: unittest.TestCase) -> int:
    """Open a local port that accepts connections (the OS completes the handshake from
    the listen backlog) but never sends a reply, like a hung sidecar. Returns the port."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test.addCleanup(listener.close)
    listener.bind(('127.0.0.1', 0))
    listener.listen(16)
    return listener.getsockname()[1]
