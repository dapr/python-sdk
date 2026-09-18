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

Turns Databricks Lakeflow streaming records into durable Dapr Workflow
executions. See ``AGENTS.md`` (architecture, delivery semantics) and
``README.md`` (usage) alongside this file for the full picture.

Importing this package never requires pyspark: only calling
``register_workflow_sink`` (or otherwise reaching into ``pyspark.pipelines``)
does, and it fails with a clear error outside a Databricks Lakeflow pipeline.
"""

from dapr.ext.databricks.batch_handler import DaprWorkflowBatchHandler
from dapr.ext.databricks.config import WorkflowSinkConfig
from dapr.ext.databricks.exceptions import (
    DaprDatabricksError,
    DaprDatabricksSinkError,
    MissingBusinessKeyError,
    SinkConfigurationError,
)
from dapr.ext.databricks.mapping import default_row_mapper
from dapr.ext.databricks.sink import register_workflow_sink

__all__ = [
    'register_workflow_sink',
    'DaprWorkflowBatchHandler',
    'WorkflowSinkConfig',
    'default_row_mapper',
    'DaprDatabricksError',
    'SinkConfigurationError',
    'MissingBusinessKeyError',
    'DaprDatabricksSinkError',
]
