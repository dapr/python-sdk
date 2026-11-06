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
"""

# A demo/test-only hook for proving crash recovery. Every trigger is `None`
# (disabled) by default, so a `DurableRAGPipeline` constructed without an
# explicit `failure_injector=` behaves exactly as it would without this
# module existing at all -- this must never be wired into a normal
# production code path. See `examples/rag/failure_demo.py` for the intended
# usage: run a worker with one trigger configured, watch it hard-exit
# mid-run, then restart the *same* worker process (with the trigger
# disabled) and observe the still-active workflow instance resume and skip
# already-completed embedding work.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import NoReturn, Optional

logger = logging.getLogger(__name__)


@dataclass
class FailureInjector:
    """Deliberately crashes the current process at a chosen point in ingestion.

    Every field is `None` (disabled) by default. At most one trigger should
    be set at a time for a given demo run.
    """

    fail_after_documents: Optional[int] = None
    """Hard-exit once more than this many `process_document` attempts have started."""

    fail_after_embedding_before_completion_for_document: Optional[str] = None
    """Hard-exit right after this document's vectors are upserted, before its
    completion record is written -- proves a redelivered activity resumes
    from state rather than re-embedding."""

    fail_during_batch_index: Optional[int] = None
    """Hard-exit right before embedding the batch at this index, for any document."""

    _processed_count: int = field(default=0, init=False, repr=False)

    def maybe_fail_before_start(self, document_id: str, attempt: int) -> None:
        """Call once per `process_document` attempt, before any real work starts."""
        if self.fail_after_documents is None:
            return
        self._processed_count += 1
        if self._processed_count > self.fail_after_documents:
            _simulate_crash(
                f'FailureInjector: simulating a crash after {self.fail_after_documents} '
                f'document(s) (triggered while starting {document_id!r}, attempt {attempt}).'
            )

    def maybe_fail_during_embedding(self, document_id: str, batch_index: int) -> None:
        """Call immediately before embedding one batch of a document's chunks."""
        if self.fail_during_batch_index is not None and batch_index == self.fail_during_batch_index:
            _simulate_crash(
                f'FailureInjector: simulating a crash during embedding batch {batch_index} '
                f'of {document_id!r}.'
            )

    def maybe_fail_after_embedding_before_completion(
        self, document_id: str, batch_index: int
    ) -> None:
        """Call immediately after a batch's vectors are durably upserted."""
        if self.fail_after_embedding_before_completion_for_document == document_id:
            _simulate_crash(
                f'FailureInjector: simulating a crash after embedding batch {batch_index} of '
                f'{document_id!r} but before its completion record is written.'
            )


def _simulate_crash(message: str) -> NoReturn:
    logger.warning(message)
    # os._exit (not sys.exit) skips atexit handlers and finally blocks, which is
    # the point: a real process crash or `kill -9` gets neither, and the demo
    # is only meaningful if recovery doesn't depend on graceful-shutdown code.
    os._exit(70)
