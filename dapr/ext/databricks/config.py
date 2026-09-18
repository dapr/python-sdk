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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from dapr.ext.databricks._typing import InstanceIdFactory, RowMapper
from dapr.ext.databricks.exceptions import SinkConfigurationError
from dapr.ext.databricks.mapping import default_row_mapper


@dataclass(frozen=True)
class WorkflowSinkConfig:
    """Configuration for a single Lakeflow-to-Dapr-Workflow sink.

    See ``register_workflow_sink`` for the parameter descriptions this
    mirrors, and ``dapr/ext/databricks/AGENTS.md`` for the delivery- and
    full-refresh-semantics this configuration controls.
    """

    name: str
    workflow: str
    id_field: Optional[str] = None
    id_fields: Optional[Sequence[str]] = None
    namespace: str = 'default'
    generation: str = 'v1'
    input_mapper: Optional[RowMapper] = None
    instance_id_factory: Optional[InstanceIdFactory] = None
    metadata: bool = True
    max_in_flight: int = 8
    max_records_per_batch: Optional[int] = None
    host: Optional[str] = None
    port: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name:
            raise SinkConfigurationError('name must be a non-empty string')
        if not self.workflow:
            raise SinkConfigurationError('workflow must be a non-empty string')
        if not self.namespace:
            raise SinkConfigurationError('namespace must be a non-empty string')
        if not self.generation:
            raise SinkConfigurationError('generation must be a non-empty string')

        key_strategies_given = sum(
            strategy is not None
            for strategy in (self.id_field, self.id_fields, self.instance_id_factory)
        )
        if key_strategies_given > 1:
            raise SinkConfigurationError(
                'specify at most one of id_field, id_fields, or instance_id_factory'
            )
        if self.id_fields is not None and len(self.id_fields) == 0:
            raise SinkConfigurationError('id_fields must not be empty')

        if self.max_in_flight < 1:
            raise SinkConfigurationError('max_in_flight must be >= 1')
        if self.max_records_per_batch is not None and self.max_records_per_batch < 1:
            raise SinkConfigurationError('max_records_per_batch must be >= 1 when set')

    @property
    def row_mapper(self) -> RowMapper:
        """The effective row mapper: the configured ``input_mapper``, or the default."""
        return self.input_mapper or default_row_mapper
