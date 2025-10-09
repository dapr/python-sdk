# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the specific language governing permissions and
limitations under the License.
"""

import os
import time

import pytest

from dapr.ext.workflow import (
    AsyncWorkflowContext,
    DaprWorkflowClient,
    DaprWorkflowContext,
    WorkflowActivityContext,
    WorkflowRuntime,
)

"""
Integration micro-benchmark using real activities via the sidecar.

Skips by default. Enable with RUN_INTEGRATION_BENCH=1 and ensure a sidecar
with workflows enabled is running and DURABLETASK_GRPC_ENDPOINT is set.
"""

skip_bench = pytest.mark.skipif(
    os.getenv('RUN_INTEGRATION_BENCH', '0') != '1',
    reason='Set RUN_INTEGRATION_BENCH=1 to run integration benchmark',
)


@skip_bench
def test_real_activity_benchmark():
    runtime = WorkflowRuntime()

    @runtime.activity(name='echo')
    def echo_act(ctx: WorkflowActivityContext, x: int) -> int:
        return x

    @runtime.workflow(name='gen_chain')
    def gen_chain(ctx: DaprWorkflowContext, num_steps: int) -> int:
        total = 0
        for i in range(num_steps):
            total += yield ctx.call_activity(echo_act, input=i)
        return total

    @runtime.async_workflow(name='async_chain')
    async def async_chain(ctx: AsyncWorkflowContext, num_steps: int) -> int:
        total = 0
        for i in range(num_steps):
            total += await ctx.call_activity(echo_act, input=i)
        return total

    runtime.start()
    try:
        try:
            runtime.wait_for_ready(timeout=15)
        except Exception:
            pass

        client = DaprWorkflowClient()
        steps = int(os.getenv('BENCH_STEPS', '100'))

        # Generator run
        gid = 'bench-gen'
        t0 = time.perf_counter()
        client.schedule_new_workflow(gen_chain, input=steps, instance_id=gid)
        state_g = client.wait_for_workflow_completion(gid, timeout_in_seconds=300)
        t_gen = time.perf_counter() - t0
        assert state_g is not None and state_g.runtime_status.name == 'COMPLETED'

        # Async run
        aid = 'bench-async'
        t1 = time.perf_counter()
        client.schedule_new_workflow(async_chain, input=steps, instance_id=aid)
        state_a = client.wait_for_workflow_completion(aid, timeout_in_seconds=300)
        t_async = time.perf_counter() - t1
        assert state_a is not None and state_a.runtime_status.name == 'COMPLETED'

        print(
            {
                'steps': steps,
                'gen_time_s': t_gen,
                'async_time_s': t_async,
                'ratio': (t_async / t_gen) if t_gen else None,
            }
        )
    finally:
        runtime.shutdown()
