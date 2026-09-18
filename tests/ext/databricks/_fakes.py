# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Shared test doubles for dapr.ext.databricks tests. Not a test module itself
(no test_ prefix), so unittest/pytest discovery skips it.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import grpc


class SimulatedRpcError(grpc.RpcError):
    """A constructible ``grpc.RpcError`` for tests, mirroring the pattern used in
    ``tests/ext/workflow/test_workflow_client.py``."""

    def __init__(self, code: Any, details: str) -> None:
        self._code = code
        self._details = details

    def code(self) -> Any:
        return self._code

    def details(self) -> str:
        return self._details


class FakeRow:
    """A minimal stand-in for ``pyspark.sql.Row``."""

    def __init__(self, **fields: Any) -> None:
        self._fields = dict(fields)

    def asDict(self, recursive: bool = False) -> Dict[str, Any]:
        if not recursive:
            return dict(self._fields)
        return {key: self._recurse(value) for key, value in self._fields.items()}

    @staticmethod
    def _recurse(value: Any) -> Any:
        if isinstance(value, FakeRow):
            return value.asDict(recursive=True)
        if isinstance(value, (list, tuple)):
            return [FakeRow._recurse(item) for item in value]
        return value

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]

    def __repr__(self) -> str:
        return f'FakeRow({self._fields!r})'


class FakeDataFrame:
    """A minimal stand-in for ``pyspark.sql.DataFrame``, backed by a plain list of rows.

    ``to_local_iterator_error``, when set, is raised by ``toLocalIterator``
    instead of iterating — used to simulate the real "toLocalIterator() is
    not supported when using file-based collect" failure observed on
    Databricks serverless / Spark Connect-backed compute, so the
    ``collect()``-based fallback path (see ``DaprWorkflowBatchHandler._iter_rows``)
    has real test coverage instead of only a local/classic-compute code path.
    """

    def __init__(
        self,
        rows: Iterable[FakeRow],
        *,
        to_local_iterator_error: Optional[BaseException] = None,
    ) -> None:
        self._rows = list(rows)
        self._to_local_iterator_error = to_local_iterator_error

    def toLocalIterator(self, prefetchPartitions: bool = False):
        if self._to_local_iterator_error is not None:
            raise self._to_local_iterator_error
        return iter(self._rows)

    def limit(self, num: int) -> 'FakeDataFrame':
        return FakeDataFrame(self._rows[:num])

    def collect(self) -> List[FakeRow]:
        return list(self._rows)


class FakeWorkflowClient:
    """An in-memory stand-in for ``DaprWorkflowClient`` that emulates the one
    invariant this extension depends on: at most one non-purged instance per
    ID, with a second ``schedule_new_workflow`` for the same ID rejected as a
    duplicate — the same behavior the real Dapr Workflow instance-start API
    documents (HTTP 409 / "already exists and is not yet reusable").

    Individual instance IDs can be configured to fail in specific ways via
    ``raise_on_get_state`` / ``raise_on_schedule``, to simulate transport,
    auth, and validation failures independently of the exists/doesn't-exist
    bookkeeping.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.existing: Set[str] = set()
        self.scheduled: List[Tuple[str, str, Any]] = []
        self.get_state_calls: List[str] = []
        self.schedule_calls: List[str] = []
        self.raise_on_get_state: Dict[str, BaseException] = {}
        self.raise_on_schedule: Dict[str, BaseException] = {}
        self.lost_response_for: Set[str] = set()
        self.closed = False

    def get_workflow_state(self, instance_id: str, *, fetch_payloads: bool = True) -> Any:
        self.get_state_calls.append(instance_id)
        if instance_id in self.raise_on_get_state:
            raise self.raise_on_get_state.pop(instance_id)
        return object() if instance_id in self.existing else None

    def schedule_new_workflow(
        self,
        workflow: str,
        *,
        input: Optional[Any] = None,
        instance_id: Optional[str] = None,
        start_at: Optional[Any] = None,
        reuse_id_policy: Optional[Any] = None,
    ) -> str:
        assert instance_id is not None
        self.schedule_calls.append(instance_id)
        with self._lock:
            if instance_id in self.existing:
                raise SimulatedRpcError(
                    grpc.StatusCode.ALREADY_EXISTS,
                    f"an active workflow with ID '{instance_id}' already exists",
                )
            if instance_id in self.raise_on_schedule:
                error = self.raise_on_schedule.pop(instance_id)
                if instance_id in self.lost_response_for:
                    # Dapr durably accepted the instance server-side, but the
                    # caller experiences this attempt as a failure (e.g. the
                    # response never arrived) — the "lost response" scenario.
                    self.existing.add(instance_id)
                raise error
            self.existing.add(instance_id)
        self.scheduled.append((workflow, instance_id, input))
        return instance_id

    def close(self) -> None:
        self.closed = True


class BarrierSyncedWorkflowClient(FakeWorkflowClient):
    """A ``FakeWorkflowClient`` that pauses every caller at the start of
    ``schedule_new_workflow`` until ``party_count`` callers have all arrived.

    Used to deterministically reproduce the "two callers race to schedule the
    same deterministic instance ID" scenario instead of relying on incidental
    thread-scheduling timing.
    """

    def __init__(self, party_count: int) -> None:
        super().__init__()
        self._barrier = threading.Barrier(party_count)

    def schedule_new_workflow(self, workflow: str, **kwargs: Any) -> str:
        self._barrier.wait(timeout=5.0)
        return super().schedule_new_workflow(workflow, **kwargs)
