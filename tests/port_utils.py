"""
Sidecar ports in tests are always pinned, never left to the Dapr CLI: the
CLI's random free-port picker can hand the same port to two listeners of one
daprd, and pinned values must sit below the OS ephemeral source-port range
(32768+ on Linux, 49152+ on macOS/Windows) or any process's outbound localhost
connection can steal them from daprd. See tests/integration/AGENTS.md.
"""

from __future__ import annotations

import socket
import sys
from typing import Iterable, NamedTuple

from tests.wait_utils import wait_until


class SidecarPorts(NamedTuple):
    """One sidecar's pinned listener ports, keyed by their ``dapr run`` flag."""

    http: int
    grpc: int
    internal_grpc: int
    metrics: int

    def as_flags(self) -> dict[str, int]:
        return {
            '--dapr-http-port': self.http,
            '--dapr-grpc-port': self.grpc,
            '--dapr-internal-grpc-port': self.internal_grpc,
            '--metrics-port': self.metrics,
        }


def _can_bind(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform != 'win32':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('', port))
        except OSError:
            return False
    return True


def wait_for_ports_free(ports: Iterable[int], *, timeout: float = 30.0) -> None:
    """Blocks until every port accepts a fresh bind.

    Gates sidecar startup on the one invariant that matters: the ports it is
    about to bind are actually free. A previous test's daprd or app draining
    past its teardown then costs a short wait here instead of a fatal
    "bind: address already in use" inside the new sidecar. SO_REUSEADDR
    mirrors daprd's own (Go) bind semantics, so TIME_WAIT does not count as
    busy.

    Raises:
        TimeoutError: listing the ports still held after ``timeout`` seconds.
    """
    pending = list(dict.fromkeys(ports))

    def _all_bindable() -> bool:
        return all(_can_bind(port) for port in pending)

    try:
        wait_until(_all_bindable, timeout=timeout, interval=0.2)
    except TimeoutError:
        ports_busy = [port for port in pending if not _can_bind(port)]
        raise TimeoutError(f'Ports still in use after {timeout}s: {ports_busy}') from None
