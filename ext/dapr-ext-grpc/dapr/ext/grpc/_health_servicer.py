import grpc
from typing import Callable, Optional

from dapr.proto import appcallback_service_v1
from dapr.proto.runtime.v1.appcallback_pb2 import HealthCheckResponse

HealthCheckCallable = Optional[Callable[[], None]]


class _HealthCheckServicer(appcallback_service_v1.AppCallbackHealthCheckServicer):
    """The implementation of HealthCheck Server.

    :class:`App` provides useful decorators to register method, topic, input bindings.
    """

    def __init__(self):
        self._health_check_cb: Optional[HealthCheckCallable] = None

    def register_health_check(self, cb: HealthCheckCallable) -> None:
        if not cb:
            raise ValueError('health check callback must be defined')
        self._health_check_cb = cb

    def HealthCheck(self, request, context):
        """Health check."""

        if not self._health_check_cb:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            context.set_details('Method not implemented!')
            raise NotImplementedError('Method not implemented!')
        self._health_check_cb()
        return HealthCheckResponse()
