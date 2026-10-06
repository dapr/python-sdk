# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Runs dapr.ext.databricks against a real Dapr sidecar (via ``dapr_env`` from
conftest.py) instead of the mocked ``DaprWorkflowClient`` the unit tests
under tests/ext/databricks use. No Databricks workspace or pyspark install
is required: Lakeflow rows/DataFrames are faked locally, the same way the
unit test suite does it (see tests/ext/databricks/_fakes.py for the
equivalent used there).
"""

import threading

import grpc
import pytest

import dapr.ext.workflow as wf
from dapr.ext.databricks import DaprWorkflowBatchHandler, WorkflowSinkConfig
from dapr.ext.databricks.exceptions import DaprDatabricksSinkError
from dapr.ext.databricks.scheduling import is_duplicate_instance_error

HOST = '127.0.0.1'
GRPC_PORT = '13501'
NAMESPACE = 'itest-orders'
SINK_NAME = 'order_actions'
WORKFLOW_NAME = 'itest_record_order'


class _FakeLakeflowRow:
    """Minimal ``pyspark.sql.Row`` stand-in; see ``dapr.ext.databricks._typing.RowLike``
    for the exact (small) surface this needs to implement."""

    def __init__(self, **fields):
        self._fields = fields

    def asDict(self, recursive=False):
        return dict(self._fields)

    def __getitem__(self, key):
        return self._fields[key]


class _FakeLakeflowBatch:
    """Minimal ``pyspark.sql.DataFrame`` micro-batch stand-in."""

    def __init__(self, rows):
        self._rows = list(rows)

    def toLocalIterator(self, prefetchPartitions=False):
        return iter(self._rows)


def _instance_id(order_id) -> str:
    return f'{NAMESPACE}-{SINK_NAME}-v1-{order_id}'


def _purge(order_ids):
    wf_client = wf.DaprWorkflowClient(host=HOST, port=GRPC_PORT)
    for order_id in order_ids:
        try:
            wf_client.purge_workflow(_instance_id(order_id))
        except Exception:
            pass
    wf_client.close()


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    return dapr_env.start_sidecar(app_id='test-databricks-sink')


@pytest.fixture(scope='module')
def execution_log():
    return []


@pytest.fixture(scope='module')
def runtime(sidecar, execution_log):
    """A tiny real Dapr Workflow app: one workflow, one activity, registered
    against the sidecar started above -- this is the "start/register a small
    workflow" step the sink is tested against."""
    lock = threading.Lock()
    rt = wf.WorkflowRuntime(host=HOST, port=GRPC_PORT)

    @rt.activity(name='itest_record_execution')
    def record_execution(ctx, order_id):
        with lock:
            execution_log.append(order_id)
        return order_id

    @rt.workflow(name=WORKFLOW_NAME)
    def record_order(ctx, envelope):
        order_id = envelope['data']['order_id']
        result = yield ctx.call_activity(record_execution, input=order_id)
        return result

    rt.start()
    rt.wait_for_worker_ready(timeout=30)
    yield rt
    rt.shutdown()


@pytest.fixture
def handler(sidecar):
    config = WorkflowSinkConfig(
        name=SINK_NAME,
        workflow=WORKFLOW_NAME,
        id_field='order_id',
        namespace=NAMESPACE,
        host=HOST,
        port=GRPC_PORT,
    )
    h = DaprWorkflowBatchHandler(config)
    yield h
    h.close()


def test_batch_schedules_one_workflow_per_row_and_retry_creates_no_duplicates(
    runtime, handler, execution_log
):
    order_ids = ['ITEST-1', 'ITEST-2']
    _purge(order_ids)
    execution_log.clear()

    def _batch():
        return _FakeLakeflowBatch([_FakeLakeflowRow(order_id=oid) for oid in order_ids])

    # 1. Pass fake Lakeflow rows through the sink handler -- schedules two new
    #    workflow instances against the real sidecar.
    handler.process(_batch(), batch_id=1)

    # 2. Verify the workflows were created and actually ran to completion.
    wf_client = wf.DaprWorkflowClient(host=HOST, port=GRPC_PORT)
    for order_id in order_ids:
        state = wf_client.wait_for_workflow_completion(
            _instance_id(order_id), timeout_in_seconds=30
        )
        assert state is not None
        assert state.runtime_status.name == 'COMPLETED'
    assert sorted(execution_log) == sorted(order_ids)

    # 3. Retry the identical micro-batch -- what a Lakeflow retry after a
    #    worker restart looks like.
    handler.process(_batch(), batch_id=1)

    # 4. Verify no duplicate workflows were created: the activity never ran a
    #    second time for either order, proving the retry was recognized as
    #    already-handled rather than executing a second instance.
    assert sorted(execution_log) == sorted(order_ids)

    wf_client.close()


def test_duplicate_schedule_is_rejected_by_real_dapr_and_recognized(runtime):
    """Validates scheduling.is_duplicate_instance_error against the actual
    Dapr sidecar response (not the simulated fakes tests/ext/databricks uses)."""
    wf_client = wf.DaprWorkflowClient(host=HOST, port=GRPC_PORT)
    instance_id = f'{NAMESPACE}-duplicate-check'
    try:
        wf_client.purge_workflow(instance_id)
    except Exception:
        pass

    wf_client.schedule_new_workflow(
        WORKFLOW_NAME, input={'data': {'order_id': 'dup-check'}}, instance_id=instance_id
    )

    with pytest.raises(grpc.RpcError) as exc_info:
        wf_client.schedule_new_workflow(
            WORKFLOW_NAME, input={'data': {'order_id': 'dup-check'}}, instance_id=instance_id
        )

    assert is_duplicate_instance_error(exc_info.value)
    wf_client.close()


def test_missing_business_key_fails_the_batch(handler):
    bad_row = _FakeLakeflowRow(customer_id=1)  # no order_id
    with pytest.raises(DaprDatabricksSinkError):
        handler.process(_FakeLakeflowBatch([bad_row]), batch_id=2)
