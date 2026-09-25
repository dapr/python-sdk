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

import asyncio
from unittest.mock import Mock, patch

import grpc
import pytest

from dapr.ext.workflow._durabletask.aio.client import AsyncTaskHubGrpcClient
from dapr.ext.workflow._durabletask.aio.internal.grpc_interceptor import (
    DefaultClientInterceptorImpl,
)
from dapr.ext.workflow._durabletask.aio.internal.shared import get_grpc_aio_channel
from dapr.ext.workflow._durabletask.internal.shared import get_default_host_address

HOST_ADDRESS = 'localhost:50051'
METADATA = [('key1', 'value1'), ('key2', 'value2')]
INTERCEPTORS_AIO = [DefaultClientInterceptorImpl(METADATA)]


def _make_async_rpc_error(code: grpc.StatusCode) -> grpc.RpcError:
    err = grpc.RpcError()
    err.code = lambda: code  # type: ignore[method-assign]
    err.details = lambda: f'simulated {code.name}'  # type: ignore[method-assign]
    return err


def test_get_grpc_aio_channel_insecure():
    with patch(
        'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
    ) as mock_channel:
        get_grpc_aio_channel(HOST_ADDRESS, False, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None


def test_get_grpc_aio_channel_secure():
    with (
        patch(
            'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.secure_channel'
        ) as mock_channel,
        patch('grpc.ssl_channel_credentials') as mock_credentials,
    ):
        get_grpc_aio_channel(HOST_ADDRESS, True, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert args[1] == mock_credentials.return_value
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None


def test_get_grpc_aio_channel_default_host_address():
    with patch(
        'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
    ) as mock_channel:
        get_grpc_aio_channel(None, False, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == get_default_host_address()
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None


def test_get_grpc_aio_channel_with_interceptors():
    with patch(
        'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
    ) as mock_channel:
        get_grpc_aio_channel(HOST_ADDRESS, False, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        # Capture and check the arguments passed to insecure_channel()
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert 'interceptors' in kwargs
        interceptors = kwargs['interceptors']
        assert isinstance(interceptors[0], DefaultClientInterceptorImpl)
        assert interceptors[0]._metadata == METADATA


def test_grpc_aio_channel_with_host_name_protocol_stripping():
    with (
        patch(
            'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
        ) as mock_insecure_channel,
        patch(
            'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.secure_channel'
        ) as mock_secure_channel,
    ):
        host_name = 'myserver.com:1234'

        prefix = 'grpc://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'http://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'HTTP://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'GRPC://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = ''
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'grpcs://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'https://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'HTTPS://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = 'GRPCS://'
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None

        prefix = ''
        get_grpc_aio_channel(prefix + host_name, True, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get('interceptors') == INTERCEPTORS_AIO
        assert 'options' in kwargs and kwargs['options'] is None


def test_async_client_construct_with_metadata():
    with patch(
        'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
    ) as mock_channel:
        client = AsyncTaskHubGrpcClient(host_address=HOST_ADDRESS, metadata=METADATA)
        assert mock_channel.call_count == 0  # channel is built lazily, not at construction

        client._get_stub()

        # Ensure channel created with an interceptor that has the expected metadata
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert 'interceptors' in kwargs
        interceptors = kwargs['interceptors']
        assert isinstance(interceptors[0], DefaultClientInterceptorImpl)
        assert interceptors[0]._metadata == METADATA


def test_async_client_channel_is_lazy():
    with patch(
        'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
    ) as mock_channel:
        client = AsyncTaskHubGrpcClient(host_address=HOST_ADDRESS)
        assert mock_channel.call_count == 0  # not built at construction

        client._get_stub()
        client._get_stub()
        assert mock_channel.call_count == 1  # built once on first use, then cached


def test_aio_channel_passes_base_options_and_max_lengths():
    base_options = [
        ('grpc.max_send_message_length', 4321),
        ('grpc.max_receive_message_length', 8765),
        ('grpc.primary_user_agent', 'durabletask-aio-tests'),
    ]
    with patch(
        'dapr.ext.workflow._durabletask.aio.internal.shared.grpc_aio.insecure_channel'
    ) as mock_channel:
        get_grpc_aio_channel(HOST_ADDRESS, False, options=base_options)
        # Ensure called with options kwarg
        assert mock_channel.call_count == 1
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert 'options' in kwargs
        opts = kwargs['options']
        # Check our base options made it through
        assert ('grpc.max_send_message_length', 4321) in opts
        assert ('grpc.max_receive_message_length', 8765) in opts
        assert ('grpc.primary_user_agent', 'durabletask-aio-tests') in opts


async def test_cancelled_after_deadline_surfaces_as_timeout():
    """Async mirror of the sync deadline-cancellation mapping.

    This is the path that actually failed in CI against daprd from master
    (test_orchestration_e2e_async.py::test_suspend_and_resume): the bounded wait
    expired as CANCELLED rather than DEADLINE_EXCEEDED and escaped as a raw
    AioRpcError instead of TimeoutError.
    """

    async def cancel_after_budget_spent(*args, **kwargs):
        await asyncio.sleep(0.05)  # outlast the caller's budget, as a real expiry would
        raise _make_async_rpc_error(grpc.StatusCode.CANCELLED)

    client = AsyncTaskHubGrpcClient()
    client._stub = Mock()
    client._stub.WaitForInstanceCompletion = cancel_after_budget_spent

    with pytest.raises(TimeoutError):
        await client.wait_for_orchestration_completion('test-instance', timeout=0.01)


async def test_cancelled_within_deadline_still_propagates():
    """A CANCELLED with budget remaining is a real cancellation, not a timeout."""

    async def cancel_immediately(*args, **kwargs):
        raise _make_async_rpc_error(grpc.StatusCode.CANCELLED)

    client = AsyncTaskHubGrpcClient()
    client._stub = Mock()
    client._stub.WaitForInstanceCompletion = cancel_immediately

    with pytest.raises(grpc.RpcError) as exc_info:
        await client.wait_for_orchestration_completion('test-instance', timeout=300)
    assert not isinstance(exc_info.value, TimeoutError)
