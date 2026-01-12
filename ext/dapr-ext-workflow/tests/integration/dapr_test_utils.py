# -*- coding: utf-8 -*-

"""
Utility functions for Dapr integration/e2e tests.

Provides helpers for starting Dapr sidecars and managing test infrastructure during integratino (e2e) tests
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time

import pytest


def is_dapr_cli_available() -> bool:
    """Check if the Dapr CLI is installed and available."""
    return shutil.which('dapr') is not None


# Skip decorator for tests that require Dapr CLI
skip_if_no_dapr = pytest.mark.skipif(
    not is_dapr_cli_available(),
    reason='Dapr CLI is not installed. Install from https://docs.dapr.io/getting-started/install-dapr-cli/',
)


def is_runtime_available(host: str, port: int) -> bool:
    """Check if a Dapr runtime is available at the given host:port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def start_dapr_sidecar(
    app_id: str, grpc_port: int, http_port: int, keep_alive_seconds: int = 600
) -> subprocess.Popen:
    """Start a Dapr sidecar using dapr CLI.

    Args:
        app_id: Application ID for the Dapr sidecar
        grpc_port: gRPC port for Dapr API
        http_port: HTTP port for Dapr API

    Returns:
        Process handle for the Dapr sidecar

    Raises:
        RuntimeError: If the sidecar fails to start
    """
    # Create temporary components directory with state store
    components_dir = tempfile.mkdtemp(prefix=f'dapr-components-{app_id}-')
    statestore_path = os.path.join(components_dir, 'statestore.yaml')

    statestore_yaml = """apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  version: v1
  metadata:
  - name: redisHost
    value: localhost:6379
  - name: redisPassword
    value: ""
  - name: actorStateStore
    value: "true"
"""

    with open(statestore_path, 'w') as f:
        f.write(statestore_yaml)

    cmd = [
        'dapr',
        'run',
        '--app-id',
        app_id,
        '--dapr-grpc-port',
        str(grpc_port),
        '--dapr-http-port',
        str(http_port),
        '--resources-path',
        components_dir,
        '--log-level',
        'info',
        '--',
        'sleep',
        str(keep_alive_seconds),
    ]

    print(
        f'[Setup] Starting dapr for {app_id} on grpc={grpc_port}, http={http_port} with components in {components_dir}',
        flush=True,
    )

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Wait for sidecar to start
    for i in range(30):  # 30 second timeout
        poll_result = proc.poll()
        if poll_result is not None:
            raise RuntimeError(f'dapr run for {app_id} exited with code {poll_result}')
        if is_runtime_available('127.0.0.1', grpc_port):
            print(f'[Setup] dapr for {app_id} is ready!', flush=True)
            # Store components directory for cleanup
            proc.components_dir = components_dir
            return proc
        if i % 5 == 0:
            print(f'[Setup] Waiting for dapr {app_id}... ({i}/30)', flush=True)
        time.sleep(1)

    # If we get here, it failed
    proc.kill()
    raise RuntimeError(f'Failed to start dapr for {app_id} - timeout after 30s')


def stop_dapr_sidecar(proc: subprocess.Popen, app_id: str):
    """Stop a dapr sidecar process.

    Args:
        proc: Process handle for the Dapr sidecar
        app_id: Application ID (for logging)
    """
    print(f'[Cleanup] Stopping dapr for {app_id}', flush=True)
    try:
        proc.terminate()
        proc.wait(timeout=5)
        print(f'[Cleanup] dapr for {app_id} stopped', flush=True)
    except subprocess.TimeoutExpired:
        print(f'[Cleanup] Force killing dapr for {app_id}', flush=True)
        proc.kill()
        proc.wait()

    # Clean up temporary components directory if it exists
    if hasattr(proc, 'components_dir'):
        try:
            shutil.rmtree(proc.components_dir)
        except Exception:
            pass


def dapr_sidecar_fixture(
    app_id: str, grpc_port: int, http_port: int, keep_alive_seconds: int = 600
):
    """Create a pytest fixture for a Dapr sidecar.

    This is a fixture factory that can be used to create reusable sidecar fixtures.

    Example:
        @pytest.fixture(scope='module')
        def my_dapr_sidecar():
            return dapr_sidecar_fixture('my-app', 50001, 3001)

    Args:
        app_id: Application ID for the Dapr sidecar
        grpc_port: gRPC port for Dapr API
        http_port: HTTP port for Dapr API

    Yields:
        Process handle for the Dapr sidecar
    """
    proc = None
    try:
        print(
            f'[Setup] Starting dapr for {app_id} on grpc={grpc_port}, http={http_port}', flush=True
        )
        proc = start_dapr_sidecar(app_id, grpc_port, http_port, keep_alive_seconds)
        yield proc
    except Exception as e:
        pytest.skip(f'Could not start dapr for {app_id}: {e}')
    finally:
        if proc:
            stop_dapr_sidecar(proc, app_id)
