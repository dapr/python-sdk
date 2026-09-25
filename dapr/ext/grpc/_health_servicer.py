from typing import Awaitable, Callable, Optional

import grpc

from dapr.ext.grpc._servicer import _ServicerContext
from dapr.proto import appcallback_service_v1
from dapr.proto.runtime.v1.appcallback_pb2 import HealthCheckResponse

HealthCheckCallable = Optional[Callable[[], None]]
# The asyncio servicer awaits its callback, so it also accepts an awaitable-returning one.
AsyncHealthCheckCallable = Callable[[], Optional[Awaitable[None]]]


class _HealthCheckServicerBase(appcallback_service_v1.AppCallbackHealthCheckServicer):
    """Health check registration shared by the sync and asyncio servicers.

    Mirrors the :class:`_CallbackServicerBase` arrangement: everything that does not invoke
    the callback lives here, and each servicer supplies only the gRPC entry point.
    """

    def __init__(self):
        self._health_check_cb: Optional[AsyncHealthCheckCallable] = None

    def register_health_check(self, cb: Optional[AsyncHealthCheckCallable]) -> None:
        if not cb:
            raise ValueError('health check callback must be defined')
        self._health_check_cb = cb

    def _require_health_check_cb(self, context: _ServicerContext) -> AsyncHealthCheckCallable:
        """Returns the registered callback, or marks the RPC UNIMPLEMENTED if there is none."""
        if not self._health_check_cb:
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)  # type: ignore
            context.set_details('Method not implemented!')
            raise NotImplementedError('Method not implemented!')
        return self._health_check_cb


class _HealthCheckServicer(_HealthCheckServicerBase):
    """The synchronous HealthCheck servicer.

    Shares registration with the asyncio servicer via their common base; only this gRPC entry
    point differs, calling the callback directly rather than awaiting it.
    """

    def HealthCheck(self, request, context):
        """Health check."""
        health_check = self._require_health_check_cb(context)
        health_check()
        return HealthCheckResponse()
