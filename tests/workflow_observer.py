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

"""A gRPC interceptor that observes how the sidecar delivers workflow history.

Mirrors the Go equivalent in dapr's integration framework
(``tests/integration/framework/process/workflow/worker.go``): every ``WorkflowRequest``
arrives either as a delta (``cachedHistory`` set, ``pastEvents`` carrying only the events
since the worker was last brought up to date) or as a full send, and every
``GetInstanceHistory`` call is a cache miss the worker had to recover from.

Without this, an e2e test cannot tell a working delta path from a sidecar that ignored
``WORKER_CAPABILITY_STATEFUL_HISTORY`` entirely: both produce identical workflow output.
"""

import threading
from typing import Any, Iterator

import grpc

_GET_WORK_ITEMS = '/TaskHubSidecarService/GetWorkItems'
_GET_INSTANCE_HISTORY = '/TaskHubSidecarService/GetInstanceHistory'


class DeliveryCounts:
    """How one instance's work items were delivered."""

    __slots__ = ('deltas', 'full_sends', 'history_fetches')

    def __init__(self) -> None:
        self.deltas = 0
        self.full_sends = 0
        self.history_fetches = 0

    def __repr__(self) -> str:
        return (
            f'DeliveryCounts(deltas={self.deltas}, full_sends={self.full_sends}, '
            f'history_fetches={self.history_fetches})'
        )


class _ObservedStream:
    """Wraps a work-item stream so each item is counted as it is read.

    Delegates every other attribute to the underlying call: the worker's failure path
    calls ``cancel()`` on the stream object, which a bare generator would not expose.
    """

    def __init__(self, call: Any, observer: 'WorkItemObserver') -> None:
        self._call = call
        self._observer = observer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._call, name)

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        work_item = next(self._call)
        self._observer.record_work_item(work_item)
        return work_item


class WorkItemObserver(grpc.UnaryUnaryClientInterceptor, grpc.UnaryStreamClientInterceptor):
    """Counts delta vs full work-item delivery, per instance and in total.

    Counters are read from the test's thread while the worker's reader thread writes them,
    hence the lock. Pass an instance via ``WorkflowRuntime(interceptors=[observer])``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._per_instance: dict[str, DeliveryCounts] = {}

    def counts_for(self, instance_id: str) -> DeliveryCounts:
        """Returns a snapshot of one instance's delivery counts."""
        with self._lock:
            counts = self._per_instance.get(instance_id)
            snapshot = DeliveryCounts()
            if counts is not None:
                snapshot.deltas = counts.deltas
                snapshot.full_sends = counts.full_sends
                snapshot.history_fetches = counts.history_fetches
            return snapshot

    def record_work_item(self, work_item: Any) -> None:
        """Classifies a received work item as a delta or a full history send."""
        if not work_item.HasField('workflowRequest'):
            return
        request = work_item.workflowRequest
        with self._lock:
            counts = self._per_instance.setdefault(request.instanceId, DeliveryCounts())
            if request.HasField('cachedHistory'):
                counts.deltas += 1
                return
            counts.full_sends += 1

    def _record_history_fetch(self, instance_id: str) -> None:
        with self._lock:
            counts = self._per_instance.setdefault(instance_id, DeliveryCounts())
            counts.history_fetches += 1

    def intercept_unary_stream(self, continuation, client_call_details, request):
        call = continuation(client_call_details, request)
        if client_call_details.method != _GET_WORK_ITEMS:
            return call
        return _ObservedStream(call, self)

    def intercept_unary_unary(self, continuation, client_call_details, request):
        if client_call_details.method == _GET_INSTANCE_HISTORY:
            self._record_history_fetch(request.instanceId)
        return continuation(client_call_details, request)
