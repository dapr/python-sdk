from collections import namedtuple
from typing import List, Optional, Tuple, Union

from grpc import (  # type: ignore
    ClientCallDetails,
    StreamStreamClientInterceptor,
    StreamUnaryClientInterceptor,
    UnaryStreamClientInterceptor,
    UnaryUnaryClientInterceptor,
)

from dapr.conf import settings


class _ClientCallDetails(
    namedtuple(
        '_ClientCallDetails',
        ['method', 'timeout', 'metadata', 'credentials', 'wait_for_ready', 'compression'],
    ),
    ClientCallDetails,
):
    """This is an implementation of the ClientCallDetails interface needed for interceptors.
    This class takes six named values and inherits the ClientCallDetails from grpc package.
    This class encloses the values that describe a RPC to be invoked.
    """

    pass


# Workflow RPCs that block until the instance starts or finishes, which can take hours.
# The caller's own timeout argument bounds them; DAPR_API_TIMEOUT_SECONDS must not, or a
# wait with no timeout would fail after that many seconds while the workflow still runs.
_UNBOUNDED_WAIT_METHODS = (
    '/TaskHubSidecarService/WaitForInstanceStart',
    '/TaskHubSidecarService/WaitForInstanceCompletion',
)


def _is_unbounded_wait(method: Union[str, bytes]) -> bool:
    if isinstance(method, bytes):
        method = method.decode('utf-8', errors='replace')
    return method in _UNBOUNDED_WAIT_METHODS


def _validate_timeout_seconds(timeout_seconds: Optional[float]) -> Optional[float]:
    if timeout_seconds is None:
        return None
    if timeout_seconds <= 0:
        raise ValueError(f'timeout_seconds must be greater than 0, got {timeout_seconds}')
    return float(timeout_seconds)


def _resolve_timeout_seconds(timeout_seconds: Optional[float]) -> Optional[float]:
    if timeout_seconds is not None:
        return timeout_seconds
    if settings.DAPR_API_TIMEOUT_SECONDS is None:
        return None
    return float(settings.DAPR_API_TIMEOUT_SECONDS)


class DaprClientTimeoutInterceptor(UnaryUnaryClientInterceptor):
    """Applies a default deadline to unary calls that do not set their own.

    Calls that already carry a timeout keep it, and the workflow waits in
    ``_UNBOUNDED_WAIT_METHODS`` are never given a default deadline.
    """

    def __init__(self, timeout_seconds: Optional[float] = None):
        """Initializes the interceptor.

        Args:
            timeout_seconds: Default deadline in seconds for calls made through this
                interceptor. ``None`` falls back to ``settings.DAPR_API_TIMEOUT_SECONDS``,
                read on every call; when that is also ``None`` no deadline is applied.

        Raises:
            ValueError: If ``timeout_seconds`` is not greater than 0.
        """
        self._timeout_seconds = _validate_timeout_seconds(timeout_seconds)

    def intercept_unary_unary(self, continuation, client_call_details, request):
        # Only apply a deadline when one is explicitly configured, here or through
        # DAPR_API_TIMEOUT_SECONDS. Without one there is no SDK-level default deadline: Dapr's
        # own resiliency policies and component timeouts act as the authoritative bounds for
        # long-running operations such as LLM calls and workflow activities.
        timeout_seconds = _resolve_timeout_seconds(self._timeout_seconds)
        if (
            timeout_seconds is not None
            and client_call_details.timeout is None
            and not _is_unbounded_wait(client_call_details.method)
        ):
            new_client_call_details = _ClientCallDetails(
                client_call_details.method,
                timeout_seconds,
                client_call_details.metadata,
                client_call_details.credentials,
                client_call_details.wait_for_ready,
                client_call_details.compression,
            )
            return continuation(new_client_call_details, request)

        return continuation(client_call_details, request)


class DaprClientInterceptor(
    UnaryUnaryClientInterceptor,
    StreamStreamClientInterceptor,
    StreamUnaryClientInterceptor,
    UnaryStreamClientInterceptor,
):
    """The class implements a UnaryUnaryClientInterceptor from grpc to add an interceptor to add
    additional headers to all calls as needed.

    Per-call API tokens take precedence over configured tokens.

    Examples:

        interceptor = HeaderInterceptor([('header', 'value', )])
        intercepted_channel = grpc.intercept_channel(grpc_channel, interceptor)

    With multiple header values:

        interceptor = HeaderInterceptor([('header1', 'value1', ), ('header2', 'value2', )])
        intercepted_channel = grpc.intercept_channel(grpc_channel, interceptor)
    """

    def __init__(self, metadata: List[Tuple[str, str]]):
        """Initializes the metadata field for the class.

        Args:
            metadata list[tuple[str, str]]: list of tuple of (key, value) strings
            representing header values
        """

        self._metadata = metadata

    def _intercept_call(self, client_call_details: ClientCallDetails) -> ClientCallDetails:
        """Internal intercept_call implementation which adds metadata to grpc metadata in the RPC
        call details.

        Args:
            client_call_details :class: `ClientCallDetails`: object that describes a RPC
            to be invoked

        Returns:
            :class: `ClientCallDetails` modified call details
        """

        metadata = []
        if client_call_details.metadata is not None:
            metadata = list(client_call_details.metadata)
        for header in self._metadata:
            if header[0] == 'dapr-api-token' and any(k == 'dapr-api-token' for k, _ in metadata):
                continue
            metadata.append(header)

        new_call_details = _ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
            client_call_details.compression,
        )
        return new_call_details

    def intercept_unary_unary(self, continuation, client_call_details, request):
        """This method intercepts a unary-unary gRPC call. It is the implementation of the
        abstract method defined in UnaryUnaryClientInterceptor defined in grpc. It's invoked
        automatically by grpc based on the order in which interceptors are added to the channel.

        Args:
            continuation: a callable to be invoked to continue with the RPC or next interceptor
            client_call_details: a ClientCallDetails object describing the outgoing RPC
            request: the request value for the RPC

        Returns:
            A response object after invoking the continuation callable
        """
        new_call_details = self._intercept_call(client_call_details)
        # Call continuation
        response = continuation(new_call_details, request)
        return response

    def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        """This method intercepts a stream-stream gRPC call. It is the implementation of the
        abstract method defined in StreamStreamClientInterceptor defined in grpc. It's invoked
        automatically by grpc based on the order in which interceptors are added to the channel.

        Args:
            continuation: a callable to be invoked to continue with the RPC or next interceptor
            client_call_details: a ClientCallDetails object describing the outgoing RPC
            request_iterator: the request value for the RPC

        Returns:
            A response object after invoking the continuation callable
        """
        new_call_details = self._intercept_call(client_call_details)
        # Call continuation
        response = continuation(new_call_details, request_iterator)
        return response

    def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        return continuation(self._intercept_call(client_call_details), request_iterator)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        return continuation(self._intercept_call(client_call_details), request)
