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

"""Watches ingestion status live, for the failure-and-resume demo.

This script doesn't itself crash anything -- `worker.py` does that, via
`FailureInjector`, when one of the `RAG_DEMO_FAIL_*` environment variables is
set (see config.py's `build_demo_failure_injector` and README.md's "Failure
and resume demo" section for the full step-by-step). Run this alongside the
worker and `cli.py start`, with the **same** `--app-id` as the worker (see
README.md's "Running the worker and CLI" section for why), to watch
`embedding_requests` and `avoided_embedding_units` live across a crash and
restart:

    dapr run --app-id rag-worker --resources-path components/ -- python3 failure_demo.py --version demo

Ctrl+C to stop watching (this never touches the pipeline itself).
"""

from __future__ import annotations

import argparse
import time

from config import build_pipeline


def watch(version: str, *, interval_seconds: float) -> None:
    pipeline = build_pipeline()
    try:
        print(f'Watching pipeline status for version={version!r} (Ctrl+C to stop)...\n')
        last_line = None
        while True:
            status = pipeline.get_status(version)
            if status is None:
                line = f'[{_now()}] no status recorded yet'
            else:
                line = (
                    f'[{_now()}] stage={status.stage} '
                    f'documents(completed/skipped/failed/total)='
                    f'{status.completed_documents}/{status.skipped_documents}/'
                    f'{status.failed_documents}/{status.total_documents} '
                    f'embedding_requests={status.embedding_requests} '
                    f'avoided_embedding_units={status.avoided_embedding_units} '
                    f'retry_count={status.retry_count} '
                    f'active_version={pipeline.resolve_active_version()}'
                )
            if line != last_line:
                print(line, flush=True)
                last_line = line
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print('\nStopped watching.')
    finally:
        pipeline.close()


def _now() -> str:
    return time.strftime('%H:%M:%S')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--version', required=True, help='The version being ingested, e.g. demo.')
    parser.add_argument('--interval-seconds', type=float, default=2.0)
    args = parser.parse_args()
    watch(args.version, interval_seconds=args.interval_seconds)


if __name__ == '__main__':
    main()
