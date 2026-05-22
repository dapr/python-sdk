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

"""Async activities running alongside sync ones in a single workflow.

Starts three async activities that do an HTTP request, then a sync activity that
sums up the results. Shows that sync and async activities work side by side.

Run with:

    dapr run --app-id async-activities --app-protocol grpc --dapr-grpc-port 50001 \\
        -- python async_activities.py
"""

from __future__ import annotations

from time import sleep

import dapr.ext.workflow as wf
import httpx
from pydantic import BaseModel

wfr = wf.WorkflowRuntime()


class FetchRequest(BaseModel):
    url: str
    timeout_seconds: float = 5.0


class FetchResult(BaseModel):
    url: str
    status_code: int
    body_length: int


@wfr.workflow(name='parallel_fetch_workflow')
def parallel_fetch_workflow(ctx: wf.DaprWorkflowContext, urls: list[str]):
    fetch_tasks = [
        ctx.call_activity(fetch_url, input=FetchRequest(url=url).model_dump()) for url in urls
    ]
    results = yield wf.when_all(fetch_tasks)
    summary = yield ctx.call_activity(summarize_fetches, input=results)
    return summary


@wfr.activity(name='fetch_url')
async def fetch_url(ctx: wf.WorkflowActivityContext, request: FetchRequest) -> dict:
    """Async activity: fetch a URL with httpx. Multiple instances run concurrently."""
    async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
        response = await client.get(request.url)
    result = FetchResult(
        url=request.url,
        status_code=response.status_code,
        body_length=len(response.content),
    )
    print(
        f'[async] fetched {result.url} -> {result.status_code} ({result.body_length}B)', flush=True
    )
    return result.model_dump()


@wfr.activity(name='summarize_fetches')
def summarize_fetches(ctx: wf.WorkflowActivityContext, results: list[dict]) -> str:
    """Sync activity: runs in the sync-fallback thread pool. Unchanged from before."""
    total_bytes = sum(r['body_length'] for r in results)
    summary = f'fetched {len(results)} URLs, total {total_bytes} bytes'
    print(f'[sync] {summary}', flush=True)
    return summary


def main() -> None:
    urls = [
        'https://httpbin.org/uuid',
        'https://httpbin.org/get',
        'https://httpbin.org/headers',
    ]

    wfr.start()
    sleep(5)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=parallel_fetch_workflow, input=urls)
    print(f'Workflow started. Instance ID: {instance_id}')

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
    assert state is not None
    print(f'Workflow completed! Status: {state.runtime_status.name}')
    print(f'Workflow result: {state.serialized_output.strip(chr(34))}')

    wfr.shutdown()


if __name__ == '__main__':
    main()
