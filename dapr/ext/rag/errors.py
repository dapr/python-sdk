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
"""

# Activities distinguish *retryable* failures (transient I/O, provider
# throttling) from *non-retryable* ones (invalid input, corrupt or unsupported
# documents) by exception type, via the RetryableError / NonRetryableError
# split below, rather than through a Dapr Workflow RetryPolicy feature: the
# public `dapr.ext.workflow.RetryPolicy` has no supported way to mark
# individual exception types as non-retryable. The vendored durabletask engine
# does have one (`NonRetryableError` / `RetryPolicy.non_retryable_error_types`),
# but it is not re-exported from `dapr.ext.workflow`, and importing
# `_durabletask` from outside the extension is unsupported (see
# dapr/ext/workflow/AGENTS.md). So instead, pipeline activities catch these
# types directly: a RetryableError is re-raised so the activity's RetryPolicy
# backs off and retries the whole activity; a NonRetryableError is caught
# internally and converted into a failed DocumentOutcome, so the activity
# still returns normally and no retry budget is wasted on a failure that
# retrying cannot fix.

from __future__ import annotations


class RagError(Exception):
    """Base class for all errors raised by dapr.ext.rag."""


class OptionalDependencyError(RagError, ImportError):
    """An adapter needs a third-party package that is not installed.

    Raised at construction time (not import time) so that `import dapr.ext.rag`
    always succeeds regardless of which optional adapters are usable, and so
    that passing an already-constructed client bypasses the check entirely.
    """

    def __init__(self, *, package: str, extra: str, feature: str) -> None:
        self.package = package
        self.extra = extra
        self.feature = feature
        super().__init__(
            f"{feature} requires the optional dependency '{package}', which is not "
            f'installed. Install it with: pip install "dapr[{extra}]" -- or pass an '
            f'already-constructed client/connection to the constructor to bypass this.'
        )


class RetryableError(RagError):
    """Base class for failures that a backoff-and-retry may resolve."""


class NonRetryableError(RagError):
    """Base class for failures that retrying will not fix."""


class TransientSourceError(RetryableError):
    """A document source operation failed transiently (throttling, timeout, network)."""


class SourceNotFoundError(NonRetryableError):
    """The requested document no longer exists at the source."""


class SourceAccessDeniedError(NonRetryableError):
    """The source rejected the request as unauthorized or forbidden."""


class DocumentChangedError(RetryableError):
    """The document's ETag/version changed between discovery and download.

    Retryable because the correct recovery is to pick up the new version on a
    later run, not to index content that no longer matches the manifest's
    recorded ETag/version under stale metadata.
    """


class UnsupportedDocumentError(NonRetryableError):
    """The parser does not support this document's format."""


class DocumentParseError(NonRetryableError):
    """The parser rejected this document's content (corrupt or unreadable)."""


class TransientEmbeddingError(RetryableError):
    """The embedding provider failed transiently (HTTP 429, timeout, 5xx)."""


class InvalidEmbeddingRequestError(NonRetryableError):
    """The embedding provider rejected the request as invalid."""


class TransientGenerationError(RetryableError):
    """The answer-generation (chat completion) provider failed transiently."""


class InvalidGenerationRequestError(NonRetryableError):
    """The answer-generation provider rejected the request as invalid."""


class TransientVectorStoreError(RetryableError):
    """The vector store failed transiently (connection reset, deadline exceeded)."""


class VectorStoreError(RagError):
    """A non-transient vector store failure (bad configuration, unsupported operation)."""


class VersionValidationError(RagError):
    """A built index version failed validation against its manifest."""


class ActivationConflictError(RetryableError):
    """A concurrent writer updated the active-version pointer first (ETag conflict).

    Retryable: re-running the activity re-reads the pointer's current ETag, so
    the workflow's own `RetryPolicy` is sufficient to resolve the race without
    a bespoke inner retry loop.
    """
