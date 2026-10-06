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

"""Fraud remediation: the Databricks Lakeflow side of the dapr.ext.databricks example.

Illustrative only -- this file is meant to be a source file inside a real
Databricks Lakeflow pipeline. It is NOT executed by this repository's test
suite and cannot run locally: it needs `pyspark.pipelines` (provided by the
Databricks Lakeflow runtime, not by `pip install pyspark`), the implicit
`spark` session Lakeflow injects into pipeline source files, and a Unity
Catalog table named `detected_fraud`.

See `fraud_remediation_workflow.py` in this same directory for the Dapr
Workflow side (freeze card / notify customer / open investigation / wait for
analyst / resolve case) -- that file *is* runnable locally via `dapr run` and
is covered by `tests/examples/test_databricks.py`.
"""

from pyspark import pipelines as dp

from dapr.ext.databricks import register_workflow_sink

# Deterministic instance IDs (<namespace>-<sink>-<generation>-<transaction_id>)
# mean a Lakeflow retry of a micro-batch recognizes transactions it already
# handed off instead of starting a second remediation. See this repository's
# dapr/ext/databricks/README.md and AGENTS.md for the full delivery-semantics
# and full-refresh (generation) writeup -- in particular, why `generation`
# defaults to a fixed value instead of changing on every full pipeline
# refresh, and what to do if you deliberately want to replay fraud actions
# after one.
register_workflow_sink(
    name='fraud_actions',
    workflow='fraud_remediation',
    id_field='transaction_id',
    namespace='fraud',
)


@dp.append_flow(
    target='fraud_actions',
    name='fraud_action_flow',
)
def fraud_action_flow():
    # `spark` is injected into pipeline source files by the Lakeflow runtime;
    # it is not something this file imports or defines.
    return spark.readStream.table('detected_fraud')  # noqa: F821
