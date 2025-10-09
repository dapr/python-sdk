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

from dapr.ext.workflow.aio import AsyncWorkflowContext, CoroutineOrchestratorRunner

skip_bench = pytest.mark.skipif(
    os.getenv('RUN_DRIVER_BENCH', '0') != '1',
    reason='Set RUN_DRIVER_BENCH=1 to run driver micro-benchmark',
)


class FakeTask:
    def __init__(self, name: str):
        self.name = name


class FakeCtx:
    def __init__(self):
        import datetime

        self.current_utc_datetime = datetime.datetime(2024, 1, 1)
        self.instance_id = 'bench'

    def create_timer(self, fire_at):
        return FakeTask('timer')


def drive(gen, steps: int):
    next(gen)
    for _ in range(steps - 1):
        try:
            gen.send(None)
        except StopIteration:
            break


def gen_orchestrator(ctx, steps: int):
    for _ in range(steps):
        yield ctx.create_timer(0)
    return 'done'


async def async_orchestrator(ctx: AsyncWorkflowContext, steps: int):
    for _ in range(steps):
        await ctx.create_timer(0)
    return 'done'


@skip_bench
def test_driver_overhead_vs_generator():
    fake = FakeCtx()
    steps = 1000

    # Generator path timing
    def gen_wrapper(ctx):
        return gen_orchestrator(ctx, steps)

    start = time.perf_counter()
    g = gen_wrapper(fake)
    drive(g, steps)
    gen_time = time.perf_counter() - start

    # Async driver timing
    runner = CoroutineOrchestratorRunner(async_orchestrator)
    start = time.perf_counter()
    ag = runner.to_generator(AsyncWorkflowContext(fake), steps)
    drive(ag, steps)
    async_time = time.perf_counter() - start

    ratio = async_time / gen_time if gen_time > 0 else float('inf')
    print({'gen_time_s': gen_time, 'async_time_s': async_time, 'ratio': ratio})
    # Assert driver overhead stays within reasonable bound
    assert ratio < 3.0
