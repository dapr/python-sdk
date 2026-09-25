#
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
#

"""Tests for the fake sidecar used by the client and actor tests.

A fake that fails to start must not leave a socket listening: unittest skips
tearDownClass when setUpClass raises, so an abandoned socket would stay open,
unserved, for the rest of the session and later tests could connect to it and hang.
"""

import os
import socket
import threading
import unittest
from typing import Callable
from unittest import mock

from tests.clients.certs import GrpcCerts, HttpCerts
from tests.clients.fake_dapr_server import FakeDaprSidecar
from tests.clients.fake_http_server import LOCALHOST, FakeHttpServer
from tests.wait_utils import wait_until


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOCALHOST, 0))
        return sock.getsockname()[1]


def _can_bind(family: socket.AddressFamily, host: str, port: int) -> bool:
    # No SO_REUSEADDR: the bind must fail while any socket is still listening on the port.
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _can_bind_http(port: int) -> bool:
    return _can_bind(socket.AF_INET, LOCALHOST, port)


def _can_bind_grpc(port: int) -> bool:
    return _can_bind(socket.AF_INET6, '::', port)


def _returns_within(seconds: float, fn: Callable[[], None]) -> bool:
    """Run fn in a daemon thread so a hang fails the test instead of the session."""
    worker = threading.Thread(target=fn, daemon=True)
    worker.start()
    worker.join(seconds)
    return not worker.is_alive()


class FakeDaprSidecarStartFailureTests(unittest.TestCase):
    def test_grpc_bind_failure_releases_http_port(self):
        http_port = _free_port()
        sidecar = FakeDaprSidecar(http_port=http_port)
        self.addCleanup(sidecar.stop)

        with mock.patch.object(
            sidecar._grpc_server,
            'add_insecure_port',
            side_effect=RuntimeError('Failed to bind to address [::]:0'),
        ):
            with self.assertRaises(RuntimeError):
                sidecar.start()

        self.assertTrue(_can_bind_http(http_port), 'HTTP port still held after failed start()')

    def test_grpc_bind_failure_on_held_port_releases_http_port(self):
        http_port = _free_port()
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as holder:
            holder.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            holder.bind(('::', 0))
            holder.listen()
            held_grpc_port = holder.getsockname()[1]

            sidecar = FakeDaprSidecar(grpc_port=held_grpc_port, http_port=http_port)
            self.addCleanup(sidecar.stop)
            with self.assertRaises(RuntimeError):
                sidecar.start()

        self.assertTrue(_can_bind_http(http_port), 'HTTP port still held after failed start()')

    def test_secure_grpc_bind_failure_releases_http_port_and_certs(self):
        http_port = _free_port()
        sidecar = FakeDaprSidecar(http_port=http_port)
        self.addCleanup(sidecar.stop_secure)

        with mock.patch.object(
            sidecar._grpc_server,
            'add_secure_port',
            side_effect=RuntimeError('Failed to bind to address [::]:0'),
        ):
            with self.assertRaises(RuntimeError):
                sidecar.start_secure()

        self.assertTrue(_can_bind_http(http_port), 'HTTP port still held after failed start()')
        self.assertFalse(os.path.exists(GrpcCerts.get_cert_path()))
        self.assertFalse(os.path.exists(HttpCerts.get_cert_path()))

    def test_http_bind_failure_releases_grpc_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
            holder.bind((LOCALHOST, 0))
            holder.listen()
            held_http_port = holder.getsockname()[1]

            sidecar = FakeDaprSidecar(http_port=held_http_port)
            self.addCleanup(sidecar.stop)
            with self.assertRaises(OSError):
                sidecar.start()

        grpc_port = sidecar.grpc_port
        self.assertNotEqual(0, grpc_port)
        wait_until(lambda: _can_bind_grpc(grpc_port), timeout=5)

    def test_stop_after_failed_grpc_bind_returns_promptly(self):
        # The HTTP server thread never started, so socketserver.shutdown() would wait
        # forever for serve_forever() to finish.
        sidecar = FakeDaprSidecar()
        with mock.patch.object(
            sidecar._grpc_server,
            'add_insecure_port',
            side_effect=RuntimeError('Failed to bind to address [::]:0'),
        ):
            with self.assertRaises(RuntimeError):
                sidecar.start()

        self.assertTrue(_returns_within(5, sidecar.stop), 'stop() hung after a failed start()')
        self.assertTrue(_returns_within(5, sidecar.stop_secure))

    def test_stop_after_failed_http_bind_returns_promptly(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
            holder.bind((LOCALHOST, 0))
            holder.listen()
            sidecar = FakeDaprSidecar(http_port=holder.getsockname()[1])
            with self.assertRaises(OSError):
                sidecar.start()

        self.assertTrue(_returns_within(5, sidecar.stop), 'stop() hung after a failed start()')


class FakeDaprSidecarLifecycleTests(unittest.TestCase):
    def test_start_reports_bound_ports_and_stop_releases_them(self):
        sidecar = FakeDaprSidecar()
        sidecar.start()
        grpc_port, http_port = sidecar.grpc_port, sidecar.http_port

        self.assertNotEqual(0, grpc_port)
        self.assertNotEqual(0, http_port)
        with socket.create_connection((LOCALHOST, http_port), timeout=5):
            pass

        sidecar.stop()
        sidecar.stop()  # a second stop is a no-op

        self.assertTrue(_can_bind_http(http_port))
        wait_until(lambda: _can_bind_grpc(grpc_port), timeout=5)

    def test_stop_without_start_returns_promptly(self):
        self.assertTrue(_returns_within(5, FakeDaprSidecar().stop))


class FakeHttpServerTests(unittest.TestCase):
    def test_shutdown_without_start_releases_port(self):
        server = FakeHttpServer()
        port = server.get_port()

        self.assertTrue(_returns_within(5, server.shutdown_server), 'shutdown_server() hung')
        self.assertTrue(_returns_within(5, server.shutdown_server))

        self.assertTrue(_can_bind_http(port))

    def test_second_server_cannot_share_a_listening_port(self):
        # HTTPServer's SO_REUSEADDR would let this bind succeed on Windows.
        server = FakeHttpServer()
        self.addCleanup(server.shutdown_server)
        server.start()

        with self.assertRaises(OSError):
            FakeHttpServer(server.get_port())


if __name__ == '__main__':
    unittest.main()
