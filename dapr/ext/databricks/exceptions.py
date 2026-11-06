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


class DaprDatabricksError(Exception):
    """Base class for all errors raised by ``dapr.ext.databricks``."""


class SinkConfigurationError(DaprDatabricksError, ValueError):
    """Raised when ``register_workflow_sink`` (or ``WorkflowSinkConfig``) is misconfigured.

    This is a caller/programming error detected before any Spark row is
    processed — e.g. specifying more than one of ``id_field``, ``id_fields``,
    and ``instance_id_factory``.
    """


class MissingBusinessKeyError(DaprDatabricksError, ValueError):
    """Raised when a configured ``id_field``/``id_fields`` is missing or null on a row.

    Treated as a malformed-record failure: it propagates out of batch
    processing so the micro-batch fails and Lakeflow retries, rather than
    silently falling back to a weaker, batch-position-based identity for a
    record the caller explicitly said should be keyed by business ID.
    """


class DaprDatabricksSinkError(DaprDatabricksError, RuntimeError):
    """Raised when a Lakeflow micro-batch cannot be durably handed off to Dapr Workflow.

    Any record for which durable acceptance (newly scheduled, or already
    present in Dapr's workflow store) could not be established causes this to
    be raised, which fails the ``foreach_batch_sink`` call and lets Lakeflow
    retry the whole micro-batch. The original failure is chained via
    ``__cause__``.
    """
