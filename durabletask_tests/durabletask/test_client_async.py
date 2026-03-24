# Copyright (c) The Dapr Authors.
# Licensed under the MIT License.

from unittest.mock import patch

from durabletask.aio.client import AsyncTaskHubGrpcClient
from durabletask.aio.internal.grpc_interceptor import DefaultClientInterceptorImpl
from durabletask.aio.internal.shared import get_grpc_aio_channel
from durabletask.internal.shared import get_default_host_address

HOST_ADDRESS = "localhost:50051"
METADATA = [("key1", "value1"), ("key2", "value2")]
INTERCEPTORS_AIO = [DefaultClientInterceptorImpl(METADATA)]


def test_get_grpc_aio_channel_insecure():
    with patch("durabletask.aio.internal.shared.grpc_aio.insecure_channel") as mock_channel:
        get_grpc_aio_channel(HOST_ADDRESS, False, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None


def test_get_grpc_aio_channel_secure():
    with (
        patch("durabletask.aio.internal.shared.grpc_aio.secure_channel") as mock_channel,
        patch("grpc.ssl_channel_credentials") as mock_credentials,
    ):
        get_grpc_aio_channel(HOST_ADDRESS, True, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert args[1] == mock_credentials.return_value
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None


def test_get_grpc_aio_channel_default_host_address():
    with patch("durabletask.aio.internal.shared.grpc_aio.insecure_channel") as mock_channel:
        get_grpc_aio_channel(None, False, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == get_default_host_address()
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None


def test_get_grpc_aio_channel_with_interceptors():
    with patch("durabletask.aio.internal.shared.grpc_aio.insecure_channel") as mock_channel:
        get_grpc_aio_channel(HOST_ADDRESS, False, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        # Capture and check the arguments passed to insecure_channel()
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert "interceptors" in kwargs
        interceptors = kwargs["interceptors"]
        assert isinstance(interceptors[0], DefaultClientInterceptorImpl)
        assert interceptors[0]._metadata == METADATA


def test_grpc_aio_channel_with_host_name_protocol_stripping():
    with (
        patch("durabletask.aio.internal.shared.grpc_aio.insecure_channel") as mock_insecure_channel,
        patch("durabletask.aio.internal.shared.grpc_aio.secure_channel") as mock_secure_channel,
    ):
        host_name = "myserver.com:1234"

        prefix = "grpc://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "http://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "HTTP://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "GRPC://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = ""
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "grpcs://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "https://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "HTTPS://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = "GRPCS://"
        get_grpc_aio_channel(prefix + host_name, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None

        prefix = ""
        get_grpc_aio_channel(prefix + host_name, True, interceptors=INTERCEPTORS_AIO)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert kwargs.get("interceptors") == INTERCEPTORS_AIO
        assert "options" in kwargs and kwargs["options"] is None


def test_async_client_construct_with_metadata():
    with patch("durabletask.aio.internal.shared.grpc_aio.insecure_channel") as mock_channel:
        AsyncTaskHubGrpcClient(host_address=HOST_ADDRESS, metadata=METADATA)
        # Ensure channel created with an interceptor that has the expected metadata
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert "interceptors" in kwargs
        interceptors = kwargs["interceptors"]
        assert isinstance(interceptors[0], DefaultClientInterceptorImpl)
        assert interceptors[0]._metadata == METADATA


def test_aio_channel_passes_base_options_and_max_lengths():
    base_options = [
        ("grpc.max_send_message_length", 4321),
        ("grpc.max_receive_message_length", 8765),
        ("grpc.primary_user_agent", "durabletask-aio-tests"),
    ]
    with patch("durabletask.aio.internal.shared.grpc_aio.insecure_channel") as mock_channel:
        get_grpc_aio_channel(HOST_ADDRESS, False, options=base_options)
        # Ensure called with options kwarg
        assert mock_channel.call_count == 1
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert "options" in kwargs
        opts = kwargs["options"]
        # Check our base options made it through
        assert ("grpc.max_send_message_length", 4321) in opts
        assert ("grpc.max_receive_message_length", 8765) in opts
        assert ("grpc.primary_user_agent", "durabletask-aio-tests") in opts
