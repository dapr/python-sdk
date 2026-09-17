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

"""Runs the DurableRAGPipeline's Dapr Workflow worker.

This process hosts the orchestrator and activities -- it's the thing that
must keep running (or be restarted) for ingestion to make progress. `cli.py`
is a separate, short-lived process that only *schedules*/*queries* runs; it
never needs this worker running in the same process.

    dapr run --app-id rag-worker --resources-path components/ -- python3 worker.py

See README.md for full setup (env vars, component YAMLs) and
failure_demo.py for how to kill and restart this process mid-run.
"""

from __future__ import annotations

import logging
import signal
import threading
from types import FrameType
from typing import Optional

from config import build_pipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('rag-worker')


def main() -> None:
    pipeline = build_pipeline()
    logger.info('Starting RAG ingestion worker (Ctrl+C to stop)...')
    pipeline.run_worker()
    logger.info('Worker ready.')

    stop_event = threading.Event()

    def _handle_shutdown_signal(signum: int, frame: Optional[FrameType]) -> None:
        logger.info('Received signal %s; shutting down...', signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    except (ValueError, AttributeError):
        pass  # SIGTERM isn't meaningfully available on every platform (e.g. Windows)

    stop_event.wait()
    pipeline.shutdown_worker()
    pipeline.close()
    logger.info('Worker stopped.')


if __name__ == '__main__':
    main()
