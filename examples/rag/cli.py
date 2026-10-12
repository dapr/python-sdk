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

"""Command-line client for the DurableRAGPipeline example.

A short-lived process: it only schedules/queries workflow runs through Dapr's
sidecar, so it needs `worker.py` running (separately, possibly on a different
machine/pod) to actually make progress. Run it with the **same** `--app-id` as
the worker -- Dapr Workflow resolves purely by that string, not by anything
else, so giving the CLI a different one silently hangs instead of erroring
(see README.md's "Running the worker and CLI" section for why):

    dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py start --version 2026-09
    dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py status --version 2026-09
    dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py resolve
    dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py activate --version 2026-09
    dapr run --app-id rag-worker --resources-path components/ -- python3 cli.py query "What is the remote work policy?"

See README.md for full setup.
"""

from __future__ import annotations

import argparse
import json

from config import build_pipeline, build_retrieval_resolver


def _cmd_start(args: argparse.Namespace) -> None:
    pipeline = build_pipeline()
    try:
        instance_id = pipeline.start(
            version=args.version,
            activate_when_complete=not args.no_activate,
            prefix=args.prefix,
        )
        print(f'Started ingestion. instance_id={instance_id}')
        print(f'Check progress with: python3 cli.py status --version {args.version}')
    finally:
        pipeline.close()


def _cmd_status(args: argparse.Namespace) -> None:
    pipeline = build_pipeline()
    try:
        status = pipeline.get_status(args.version)
    finally:
        pipeline.close()
    if status is None:
        print(f'No status recorded yet for version={args.version!r}.')
        return
    print(json.dumps(status.to_dict(), indent=2, default=str))


def _cmd_resolve(_args: argparse.Namespace) -> None:
    pipeline = build_pipeline()
    try:
        active_version = pipeline.resolve_active_version()
    finally:
        pipeline.close()
    print(active_version or '(no version activated yet)')


def _cmd_activate(args: argparse.Namespace) -> None:
    pipeline = build_pipeline()
    try:
        instance_id = pipeline.activate_version(args.version)
    finally:
        pipeline.close()
    print(f'Activation started. instance_id={instance_id}')


def _cmd_query(args: argparse.Namespace) -> None:
    resolver = build_retrieval_resolver()
    try:
        matches = resolver.query(args.question, top_k=args.top_k)
    finally:
        resolver.close()
    if not matches:
        print('No matches found (has a version been activated yet?).')
        return
    for rank, match in enumerate(matches, start=1):
        source_name = match.metadata.get('source_name', match.document_id)
        print(f'[{rank}] score={match.score:.3f} source={source_name} chunk_id={match.chunk_id}')
        print(f'    {match.content[:200]}{"..." if len(match.content) > 200 else ""}')


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    start = subparsers.add_parser('start', help='Start (or resume) an ingestion run.')
    start.add_argument(
        '--version', required=True, help='Logical index version to build, e.g. 2026-09.'
    )
    start.add_argument(
        '--prefix', default=None, help='Overrides the source-configured prefix for this run.'
    )
    start.add_argument(
        '--no-activate', action='store_true', help='Build the version without activating it.'
    )
    start.set_defaults(func=_cmd_start)

    status = subparsers.add_parser('status', help='Show ingestion status/metrics for a version.')
    status.add_argument('--version', required=True)
    status.set_defaults(func=_cmd_status)

    resolve = subparsers.add_parser('resolve', help='Print the currently active version.')
    resolve.set_defaults(func=_cmd_resolve)

    activate = subparsers.add_parser(
        'activate', help='Validate and activate an already-built version.'
    )
    activate.add_argument('--version', required=True)
    activate.set_defaults(func=_cmd_activate)

    query = subparsers.add_parser(
        'query', help='Run a sample retrieval against the active version.'
    )
    query.add_argument('question')
    query.add_argument('--top-k', type=int, default=5)
    query.set_defaults(func=_cmd_query)

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
