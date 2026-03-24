from unittest.mock import MagicMock, patch

from durabletask import client
from durabletask.internal.grpc_interceptor import DefaultClientInterceptorImpl
from durabletask.internal.shared import (
    DEFAULT_GRPC_KEEPALIVE_OPTIONS,
    get_default_host_address,
    get_grpc_channel,
)

EXPECTED_DEFAULT_OPTIONS = list(DEFAULT_GRPC_KEEPALIVE_OPTIONS)

HOST_ADDRESS = "localhost:50051"
METADATA = [("key1", "value1"), ("key2", "value2")]
INTERCEPTORS = [DefaultClientInterceptorImpl(METADATA)]


def test_get_grpc_channel_insecure():
    with patch("grpc.insecure_channel") as mock_channel:
        get_grpc_channel(HOST_ADDRESS, False, interceptors=INTERCEPTORS)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS


def test_get_grpc_channel_secure():
    with (
        patch("grpc.secure_channel") as mock_channel,
        patch("grpc.ssl_channel_credentials") as mock_credentials,
    ):
        get_grpc_channel(HOST_ADDRESS, True, interceptors=INTERCEPTORS)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert args[1] == mock_credentials.return_value
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS


def test_get_grpc_channel_default_host_address():
    with patch("grpc.insecure_channel") as mock_channel:
        get_grpc_channel(None, False, interceptors=INTERCEPTORS)
        args, kwargs = mock_channel.call_args
        assert args[0] == get_default_host_address()
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS


def test_get_grpc_channel_with_metadata():
    with (
        patch("grpc.insecure_channel") as mock_channel,
        patch("grpc.intercept_channel") as mock_intercept_channel,
    ):
        get_grpc_channel(HOST_ADDRESS, False, interceptors=INTERCEPTORS)
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS
        mock_intercept_channel.assert_called_once()

        # Capture and check the arguments passed to intercept_channel()
        args, kwargs = mock_intercept_channel.call_args
        assert args[0] == mock_channel.return_value
        assert isinstance(args[1], DefaultClientInterceptorImpl)
        assert args[1]._metadata == METADATA


def test_grpc_channel_with_host_name_protocol_stripping():
    with (
        patch("grpc.insecure_channel") as mock_insecure_channel,
        patch("grpc.secure_channel") as mock_secure_channel,
    ):
        host_name = "myserver.com:1234"

        prefix = "grpc://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "http://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "HTTP://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "GRPC://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = ""
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_insecure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "grpcs://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "https://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "HTTPS://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = "GRPCS://"
        get_grpc_channel(prefix + host_name, interceptors=INTERCEPTORS)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS

        prefix = ""
        get_grpc_channel(prefix + host_name, True, interceptors=INTERCEPTORS)
        args, kwargs = mock_secure_channel.call_args
        assert args[0] == host_name
        assert "options" in kwargs and kwargs["options"] == EXPECTED_DEFAULT_OPTIONS


def test_sync_channel_passes_base_options_and_max_lengths():
    base_options = [
        ("grpc.max_send_message_length", 1234),
        ("grpc.max_receive_message_length", 5678),
        ("grpc.primary_user_agent", "durabletask-tests"),
    ]
    with patch("grpc.insecure_channel") as mock_channel:
        get_grpc_channel(HOST_ADDRESS, False, options=base_options)
        # Ensure called with options kwarg
        assert mock_channel.call_count == 1
        args, kwargs = mock_channel.call_args
        assert args[0] == HOST_ADDRESS
        assert "options" in kwargs
        opts = kwargs["options"]
        # Check our base options made it through
        assert ("grpc.max_send_message_length", 1234) in opts
        assert ("grpc.max_receive_message_length", 5678) in opts
        assert ("grpc.primary_user_agent", "durabletask-tests") in opts


def test_taskhub_client_close_handles_exceptions():
    """Test that close() handles exceptions gracefully (edge case not easily testable in E2E)."""
    with patch("durabletask.internal.shared.get_grpc_channel") as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close.side_effect = Exception("close failed")
        mock_get_channel.return_value = mock_channel

        task_hub_client = client.TaskHubGrpcClient()
        # Should not raise exception
        task_hub_client.close()


def test_taskhub_client_close_closes_channel_handles_exceptions():
    """Test that close() closes the channel and handles exceptions gracefully."""
    with patch("durabletask.internal.shared.get_grpc_channel") as mock_get_channel:
        mock_channel = MagicMock()
        mock_channel.close.side_effect = Exception("close failed")
        mock_get_channel.return_value = mock_channel

        task_hub_client = client.TaskHubGrpcClient()
        task_hub_client.close()
        mock_channel.close.assert_called_once()
