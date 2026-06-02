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

"""Async activities running alongside a sync one in a fan-out/fan-in workflow.

Each async activity simulates an I/O-bound call: it takes a payload, awaits a fixed
delay (standing in for a network round-trip), and returns a result payload. The async
instances run concurrently on the worker's event loop; a final sync activity aggregates
the results. Fan-out width, input/output payload sizes, and the delay are configurable
via environment variables.

Run with:

    dapr run --app-id async-activities --app-protocol grpc --dapr-grpc-port 50001 \\
        -- python async_activities.py
"""

from __future__ import annotations

import asyncio
import os
import random
import string
from time import sleep

import dapr.ext.workflow as wf
from pydantic import BaseModel

FAN_OUT = int(os.environ.get('WORKFLOW_FAN_OUT', '5'))
INPUT_BYTES = int(os.environ.get('WORKFLOW_INPUT_BYTES', '2048'))
OUTPUT_BYTES = int(os.environ.get('WORKFLOW_OUTPUT_BYTES', '1024'))
IO_SECONDS = float(os.environ.get('WORKFLOW_IO_SECONDS', '1.0'))

wfr = wf.WorkflowRuntime()


def _random_digits(n: int) -> str:
    return ''.join(random.choices(string.digits, k=n))


class Payload(BaseModel):
    index: int
    data: str


@wfr.workflow(name='fan_out_fan_in_workflow')
def fan_out_fan_in_workflow(ctx: wf.DaprWorkflowContext, payloads: list[dict]):
    tasks = [ctx.call_activity(process_payload, input=p) for p in payloads]
    results = yield wf.when_all(tasks)
    summary = yield ctx.call_activity(summarize, input=results)
    return summary


@wfr.activity(name='process_payload')
async def process_payload(ctx: wf.WorkflowActivityContext, payload: Payload) -> str:
    """Async activity: simulate an I/O-bound call. Instances run concurrently on the loop."""
    await asyncio.sleep(IO_SECONDS)
    result = _random_digits(OUTPUT_BYTES)
    print(
        f'[async] payload {payload.index}: {len(payload.data)}B in -> {len(result)}B out',
        flush=True,
    )
    return result


@wfr.activity(name='summarize')
def summarize(ctx: wf.WorkflowActivityContext, results: list[str]) -> str:
    """Sync activity: aggregate the fan-out results on the thread pool."""
    total_bytes = sum(len(r) for r in results)
    total_zeros = sum(r.count('0') for r in results)
    summary = f'{len(results)} results, {total_bytes} bytes, {total_zeros} zeros'
    print(f'[sync] {summary}', flush=True)
    return summary


def main() -> None:
    payloads = [
        Payload(index=i, data=_random_digits(INPUT_BYTES)).model_dump() for i in range(FAN_OUT)
    ]

    wfr.start()
    sleep(5)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(workflow=fan_out_fan_in_workflow, input=payloads)
    print(f'Workflow started. Instance ID: {instance_id}')

    state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)
    assert state is not None
    print(f'Workflow completed! Status: {state.runtime_status.name}')
    print(f'Workflow result: {state.serialized_output.strip(chr(34))}')

    wfr.shutdown()


if __name__ == '__main__':
    main()
