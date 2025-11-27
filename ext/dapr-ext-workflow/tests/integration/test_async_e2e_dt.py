# -*- coding: utf-8 -*-

"""
Async e2e tests using durabletask worker/client directly.

These validate basic orchestration behavior against a running sidecar
to isolate environment issues from WorkflowRuntime wiring.
"""

from __future__ import annotations

import time

import pytest
from durabletask.aio import AsyncWorkflowContext
from durabletask.client import TaskHubGrpcClient
from durabletask.worker import TaskHubGrpcWorker

from .dapr_test_utils import dapr_sidecar_fixture, skip_if_no_dapr

pytestmark = [pytest.mark.e2e, skip_if_no_dapr]

# Dapr configuration for e2e tests
DAPR_GRPC_PORT = 50012
DAPR_HTTP_PORT = 3502


@pytest.fixture(scope='module')
def dapr_sidecar():
    """Start Dapr sidecar for all e2e tests in this module."""
    yield from dapr_sidecar_fixture('test-e2e-dt', DAPR_GRPC_PORT, DAPR_HTTP_PORT)


def get_workger_client_worker() -> tuple[TaskHubGrpcWorker, TaskHubGrpcClient]:
    return TaskHubGrpcWorker(host_address=f'localhost:{DAPR_GRPC_PORT}'), TaskHubGrpcClient(
        host_address=f'localhost:{DAPR_GRPC_PORT}'
    )


def test_dt_simple_activity_e2e(dapr_sidecar):
    worker, client = get_workger_client_worker()

    def act(ctx, x: int) -> int:
        return x * 3

    worker.add_activity(act)

    @worker.add_async_orchestrator
    async def orch(ctx: AsyncWorkflowContext, x: int) -> int:
        return await ctx.call_activity(act, input=x)

    worker.start()
    try:
        try:
            if hasattr(worker, 'wait_for_ready'):
                worker.wait_for_ready(timeout=10)  # type: ignore[attr-defined]
        except Exception:
            pass
        iid = f'dt-e2e-act-{int(time.time() * 1000)}'
        client.schedule_new_orchestration(orch, input=5, instance_id=iid)
        st = client.wait_for_orchestration_completion(iid, timeout=30)
        assert st is not None
        assert st.runtime_status.name == 'COMPLETED'
        # Output is JSON serialized scalar
        assert st.serialized_output.strip() in ('15', '"15"')
    finally:
        try:
            worker.stop()
        except Exception:
            pass


def test_dt_timer_e2e(dapr_sidecar):
    worker, client = get_workger_client_worker()

    @worker.add_async_orchestrator
    async def orch(ctx: AsyncWorkflowContext, delay: float) -> dict:
        start = ctx.now()
        await ctx.create_timer(delay)
        end = ctx.now()
        return {'start': start.isoformat(), 'end': end.isoformat(), 'delay': delay}

    worker.start()
    try:
        try:
            if hasattr(worker, 'wait_for_ready'):
                worker.wait_for_ready(timeout=10)  # type: ignore[attr-defined]
        except Exception:
            pass
        iid = f'dt-e2e-timer-{int(time.time() * 1000)}'
        delay = 1.0
        client.schedule_new_orchestration(orch, input=delay, instance_id=iid)
        st = client.wait_for_orchestration_completion(iid, timeout=30)
        assert st is not None
        assert st.runtime_status.name == 'COMPLETED'
    finally:
        try:
            worker.stop()
        except Exception:
            pass


def test_dt_sub_orchestrator_e2e(dapr_sidecar):
    worker, client = get_workger_client_worker()

    def act(ctx, s: str) -> str:
        return f'A:{s}'

    worker.add_activity(act)

    async def child(ctx: AsyncWorkflowContext, s: str) -> str:
        print('[E2E DEBUG] child start', s)
        try:
            res = await ctx.call_activity(act, input=s)
            print('[E2E DEBUG] child done', res)
            return res
        except Exception as exc:  # pragma: no cover - troubleshooting aid
            import traceback as _tb

            print('[E2E DEBUG] child exception:', type(exc).__name__, str(exc))
            print(_tb.format_exc())
            raise

    # Explicit registration to avoid decorator replacing symbol with a string in newer versions
    worker.add_async_orchestrator(child)

    async def parent(ctx: AsyncWorkflowContext, s: str) -> str:
        print('[E2E DEBUG] parent start', s)
        try:
            c = await ctx.call_sub_orchestrator(child, input=s)
            out = f'P:{c}'
            print('[E2E DEBUG] parent done', out)
            return out
        except Exception as exc:  # pragma: no cover - troubleshooting aid
            import traceback as _tb

            print('[E2E DEBUG] parent exception:', type(exc).__name__, str(exc))
            print(_tb.format_exc())
            raise

    worker.add_async_orchestrator(parent)

    worker.start()
    try:
        try:
            if hasattr(worker, 'wait_for_ready'):
                worker.wait_for_ready(timeout=10)  # type: ignore[attr-defined]
        except Exception:
            pass
        iid = f'dt-e2e-sub-{int(time.time() * 1000)}'
        print('[E2E DEBUG] scheduling instance', iid)
        client.schedule_new_orchestration(parent, input='x', instance_id=iid)
        st = client.wait_for_orchestration_completion(iid, timeout=30)
        assert st is not None
        if st.runtime_status.name != 'COMPLETED':
            # Print orchestration state details to aid debugging
            print('[E2E DEBUG] orchestration FAILED; details:')
            to_json = getattr(st, 'to_json', None)
            if callable(to_json):
                try:
                    print(to_json())
                except Exception:
                    pass
            print('status=', getattr(st, 'runtime_status', None))
            print('output=', getattr(st, 'serialized_output', None))
            print('failure=', getattr(st, 'failure_details', None))
        assert st.runtime_status.name == 'COMPLETED'
    finally:
        try:
            worker.stop()
        except Exception:
            pass


def test_dt_async_activity_e2e(dapr_sidecar):
    """Test async activities with actual async I/O operations."""
    worker, client = get_workger_client_worker()

    # Define an async activity that performs async work
    async def async_io_activity(ctx, x: int) -> dict:
        """Async activity that simulates I/O-bound work."""
        import asyncio

        # Simulate async I/O (e.g., network request, database query)
        await asyncio.sleep(0.01)
        result = x * 5
        await asyncio.sleep(0.01)
        return {'input': x, 'output': result, 'async': True}

    worker.add_activity(async_io_activity)

    @worker.add_async_orchestrator
    async def orch(ctx: AsyncWorkflowContext, x: int) -> dict:
        # Call async activity
        result = await ctx.call_activity(async_io_activity, input=x)
        return result

    worker.start()
    try:
        try:
            if hasattr(worker, 'wait_for_ready'):
                worker.wait_for_ready(timeout=10)  # type: ignore[attr-defined]
        except Exception:
            pass
        iid = f'dt-e2e-async-act-{int(time.time() * 1000)}'
        client.schedule_new_orchestration(orch, input=7, instance_id=iid)
        st = client.wait_for_orchestration_completion(iid, timeout=30)
        assert st is not None
        assert st.runtime_status.name == 'COMPLETED'

        # Verify the output contains expected values
        import json

        output = json.loads(st.serialized_output)
        assert output['input'] == 7
        assert output['output'] == 35
        assert output['async'] is True
    finally:
        try:
            worker.stop()
        except Exception:
            pass
