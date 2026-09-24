# -*- coding: utf-8 -*-
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

"""Debounces a burst of change events into one reconciliation run per quiet window.

Event delivery alone never proves a container's final contents (events can be
dropped, duplicated, or arrive out of order), and starting a full ingestion
run per individual blob event would be wasteful and could overlap. This
module implements the second MVP option the design calls for: a short
debounce window followed by a prefix-level reconciliation -- rather than a
per-document incremental workflow. `DurableRAGPipeline.start()`'s own
discovery step (against the real source, not the event stream) remains the
source of truth for what actually needs (re)indexing; this module's only job
is deciding *when* to call it.

`ReconciliationTrigger` below is deliberately **not** a Dapr Workflow: it
debounces with a plain `threading.Timer` inside one subscriber process, which
is correct for a single-instance subscriber (this example's deployment
shape) but does not coordinate across multiple concurrent subscriber
replicas -- each replica would debounce independently, and a production
deployment that scales the subscriber out would want the equivalent
`ctx.create_timer(...)` / `ctx.wait_for_external_event(...)` pattern inside an
actual Dapr Workflow instead (one durable "quiet window" orchestration per
prefix, restarting its timer on every new external event, matching
`examples/workflow/human_approval.py`'s wait-with-timeout shape) so exactly
one reconciliation fires regardless of replica count. Noted here rather than
implemented, to keep this example's scope matched to its single-process
demo.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from config import build_pipeline

from dapr.ext.rag.models import SourceChangeEvent

logger = logging.getLogger('rag-reconciliation')


def _default_version_for_now() -> str:
    """Buckets changes into a daily version -- replace with your own policy."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


class ReconciliationTrigger:
    """Coalesces `notify_change` calls into a single, debounced ingestion run."""

    def __init__(
        self,
        *,
        pipeline_id: str,
        debounce_seconds: float = 30.0,
        version_fn: Callable[[], str] = _default_version_for_now,
    ) -> None:
        self._pipeline_id = pipeline_id
        self._debounce_seconds = debounce_seconds
        self._version_fn = version_fn
        self._lock = threading.Lock()
        self._pending_timer: Optional[threading.Timer] = None
        self._pending_prefix: Optional[str] = None

    def notify_change(self, event: SourceChangeEvent) -> None:
        """Records a change and (re)starts the debounce window.

        Any change arriving before the window elapses cancels and restarts
        the timer, so a burst of events collapses into one reconciliation
        shortly after the burst goes quiet.
        """
        prefix = _prefix_of(event.source_document_id)
        with self._lock:
            if self._pending_timer is not None:
                self._pending_timer.cancel()
            self._pending_prefix = prefix if prefix == self._pending_prefix else None
            timer = threading.Timer(self._debounce_seconds, self._reconcile)
            timer.daemon = True
            self._pending_timer = timer
            timer.start()

    def _reconcile(self) -> None:
        version = self._version_fn()
        with self._lock:
            prefix = self._pending_prefix
            self._pending_timer = None
        logger.info(
            'Debounce window elapsed for pipeline_id=%s; starting reconciliation version=%s prefix=%s',
            self._pipeline_id,
            version,
            prefix,
        )
        pipeline = build_pipeline()
        try:
            instance_id = pipeline.start(version=version, prefix=prefix)
            logger.info('Reconciliation ingestion instance_id=%s', instance_id)
        finally:
            pipeline.close()


def _prefix_of(source_document_id: str) -> Optional[str]:
    """A conservative common-prefix guess, for status/logging only -- discovery
    always re-lists the real source, so an imprecise prefix here never causes
    incorrect indexing, only a possibly-wider-than-necessary re-scan."""
    _scheme, _, rest = source_document_id.partition('://')
    _bucket, _, key = rest.partition('/')
    return key.rsplit('/', 1)[0] + '/' if '/' in key else None
