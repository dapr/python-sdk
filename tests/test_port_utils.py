import socket
from contextlib import closing

import pytest

from tests.port_utils import SidecarPorts, wait_for_ports_free


def _listener() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 0))
    sock.listen(1)
    return sock


def test_wait_returns_once_ports_are_free() -> None:
    with closing(_listener()) as sock:
        port = sock.getsockname()[1]
    wait_for_ports_free([port], timeout=5)


def test_wait_times_out_while_a_listener_holds_the_port() -> None:
    with closing(_listener()) as sock:
        port = sock.getsockname()[1]
        with pytest.raises(TimeoutError, match=str(port)):
            wait_for_ports_free([port], timeout=0.3)


def test_sidecar_ports_map_to_dapr_run_flags() -> None:
    ports = SidecarPorts(http=13601, grpc=13602, internal_grpc=13603, metrics=13604)

    assert ports.as_flags() == {
        '--dapr-http-port': 13601,
        '--dapr-grpc-port': 13602,
        '--dapr-internal-grpc-port': 13603,
        '--metrics-port': 13604,
    }
