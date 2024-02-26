import time
from collections import namedtuple
from typing import List, Tuple

from grpc import StatusCode, UnaryUnaryClientInterceptor, RpcError, ClientCallDetails, _channel

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


class RetryPolicy:
    def __init__(self, max_retries=None, initial_backoff=None, backoff_multiplier=None):
        self.max_retries = max_retries or settings.DAPR_API_MAX_RETRIES
        self.initial_backoff = initial_backoff or 1
        self.backoff_multiplier = backoff_multiplier or 2

    def __str__(self):
        return f'RetryPolicy(max_retries={self.max_retries}, initial_backoff={self.initial_backoff}, backoff_multiplier={self.backoff_multiplier})'


class DaprRetryClientInterceptor(UnaryUnaryClientInterceptor):
    def __init__(self, retry_policy):
        self.retry_policy = retry_policy

    def intercept_unary_unary(self, continuation, client_call_details, request):
        # If max_retries is 0, then we don't retry
        if self.retry_policy.max_retries == 0:
            return continuation(client_call_details, request)

        attempt = 0
        while self.retry_policy.max_retries == -1 or attempt < self.retry_policy.max_retries:
            try:
                print(f'Trying RPC call, attempt {attempt + 1}')

                # Make the grpc unary call
                # This doesn't raise an exception, we have to manually check
                # if the response is an error
                response = continuation(client_call_details, request)
                if isinstance(response, _channel._InactiveRpcError):
                    error_code = response.code()  # Get the status code of the error

                    if error_code in (StatusCode.UNAVAILABLE, StatusCode.DEADLINE_EXCEEDED):
                        raise response

                return response
            except RpcError as err:
                if err.code() not in (StatusCode.UNAVAILABLE, StatusCode.DEADLINE_EXCEEDED):
                    raise
                if (
                    self.retry_policy.max_retries != -1
                    and attempt == self.retry_policy.max_retries - 1
                ):
                    raise
                sleep_time = self.retry_policy.initial_backoff * (
                    self.retry_policy.backoff_multiplier**attempt
                )
                print(f'Sleeping for {sleep_time} seconds before retrying RPC call')
                time.sleep(sleep_time)
                attempt += 1
        raise Exception(f'RPC call failed after {attempt} retries')


class DaprClientInterceptor(UnaryUnaryClientInterceptor):
    """The class implements a UnaryUnaryClientInterceptor from grpc to add an interceptor to add
    additional headers to all calls as needed.

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
        metadata.extend(self._metadata)

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
        """This method intercepts a unary-unary gRPC call. This is the implementation of the
        abstract method defined in UnaryUnaryClientInterceptor defined in grpc. This is invoked
        automatically by grpc based on the order in which interceptors are added to the channel.

        Args:
            continuation: a callable to be invoked to continue with the RPC or next interceptor
            client_call_details: a ClientCallDetails object describing the outgoing RPC
            request: the request value for the RPC

        Returns:
            A response object after invoking the continuation callable
        """
        # Pre-process or intercept call
        new_call_details = self._intercept_call(client_call_details)
        # Call continuation
        response = continuation(new_call_details, request)
        return response
