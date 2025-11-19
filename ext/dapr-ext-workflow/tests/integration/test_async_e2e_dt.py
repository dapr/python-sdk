# -*- coding: utf-8 -*-

"""
Async e2e tests using durabletask worker/client directly.

These validate basic orchestration behavior against a running sidecar
to isolate environment issues from WorkflowRuntime wiring.
"""

from __future__ import annotations

import os
import time

import pytest
from durabletask.aio import AsyncWorkflowContext
from durabletask.client import TaskHubGrpcClient
from durabletask.worker import TaskHubGrpcWorker

pytestmark = pytest.mark.e2e


def _is_runtime_available(ep_str: str) -> bool:
    import socket

    try:
        host, port = ep_str.split(':')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        return result == 0
    except Exception:
        return False


endpoint = os.getenv('DAPR_GRPC_ENDPOINT', 'localhost:50001')

skip_if_no_runtime = pytest.mark.skipif(
    not _is_runtime_available(endpoint),
    reason='DurableTask runtime not available',
)


@skip_if_no_runtime
def test_dt_simple_activity_e2e():
    # using global read-only endpoint variable
    worker = TaskHubGrpcWorker(host_address=endpoint)
    client = TaskHubGrpcClient(host_address=endpoint)

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


@skip_if_no_runtime
def test_dt_timer_e2e():
    # using global read-only endpoint variable
    worker = TaskHubGrpcWorker(host_address=endpoint)
    client = TaskHubGrpcClient(host_address=endpoint)

    @worker.add_async_orchestrator
    async def orch(ctx: AsyncWorkflowContext, delay: float) -> dict:
        start = ctx.now()
        await ctx.sleep(delay)
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


@skip_if_no_runtime
def test_dt_sub_orchestrator_e2e():
    # using global read-only endpoint variable
    worker = TaskHubGrpcWorker(host_address=endpoint)
    client = TaskHubGrpcClient(host_address=endpoint)

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
