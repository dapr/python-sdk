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

# Shared between OpenAIEmbedder and AzureOpenAIEmbedder: Azure OpenAI's
# embeddings API is wire-compatible with OpenAI's (same response shape, same
# `openai` Python package, same exception types), so response parsing and
# error classification live here once instead of being duplicated across the
# two client configurations.

from __future__ import annotations

import logging
from typing import Any, FrozenSet, Optional, Sequence, Type

from dapr.ext.rag.errors import (
    InvalidEmbeddingRequestError,
    NonRetryableError,
    OptionalDependencyError,
    RagError,
    RetryableError,
    TransientEmbeddingError,
)
from dapr.ext.rag.models import EmbeddingBatchResult

# See dapr/ext/rag/AGENTS.md for why the optional-dependency guard lives here,
# per adapter module, rather than once in dapr/ext/rag/__init__.py. Both
# AzureOpenAIEmbedder and generation.AzureOpenAIChatClient build their client
# through `build_azure_client` below, so the guard lives here once for both.
try:
    import openai
except ImportError:  # pragma: no cover - exercised only without openai installed
    openai = None  # type: ignore[assignment]

try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
except ImportError:  # pragma: no cover - exercised only without azure-identity installed
    DefaultAzureCredential = None  # type: ignore[assignment,misc]
    get_bearer_token_provider = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Azure OpenAI (Cognitive Services) requires this exact resource scope for
# Entra ID token acquisition -- see Microsoft's Azure OpenAI auth docs.
AAD_SCOPE = 'https://cognitiveservices.azure.com/.default'
DEFAULT_AZURE_API_VERSION = '2024-10-21'

# Classified by exception *name* rather than `isinstance` against the real
# `openai` exception classes, so this still works when a test injects a fake
# client that raises a look-alike exception without the `openai` package
# installed at all -- and so classification doesn't require importing every
# exception type individually under the same guard as the client itself.
TRANSIENT_EXCEPTION_NAMES = frozenset(
    {'RateLimitError', 'APITimeoutError', 'APIConnectionError', 'InternalServerError'}
)
INVALID_REQUEST_EXCEPTION_NAMES = frozenset(
    {
        'BadRequestError',
        'AuthenticationError',
        'PermissionDeniedError',
        'NotFoundError',
        'UnprocessableEntityError',
        'ConflictError',
    }
)


def parse_embeddings_response(response: Any) -> EmbeddingBatchResult:
    """Parses an OpenAI/Azure OpenAI `embeddings.create()` response, ordered by input index."""
    by_index = sorted(response.data, key=lambda item: item.index)
    embeddings: list[Sequence[float]] = [list(item.embedding) for item in by_index]
    usage = getattr(response, 'usage', None)
    total_tokens = getattr(usage, 'total_tokens', None)
    return EmbeddingBatchResult(embeddings=embeddings, total_tokens=total_tokens)


def classify_error(
    exc: Exception,
    *,
    extra_transient_status_codes: FrozenSet[int] = frozenset(),
    transient_cls: Type[RetryableError] = TransientEmbeddingError,
    invalid_request_cls: Type[NonRetryableError] = InvalidEmbeddingRequestError,
) -> RagError:
    """Classifies an OpenAI/Azure OpenAI SDK exception as retryable or not.

    Args:
        exc: The exception raised by the `openai` client.
        extra_transient_status_codes: HTTP statuses, beyond the universally
            transient 429/5xx, to treat as transient for this provider (e.g.
            Azure OpenAI's 408 request-timeout).
        transient_cls: The exception type to raise for a transient failure --
            embeddings and chat-completion callers use different types (see
            `errors.py`) so callers can distinguish which concern failed.
        invalid_request_cls: The exception type to raise for an invalid,
            non-retryable request.

    Returns:
        An instance of `invalid_request_cls` (non-retryable) or
        `transient_cls` (retryable), the latter carrying a
        `retry_after_seconds` attribute when the provider sent one.
    """
    name = type(exc).__name__
    retry_after = _extract_retry_after(exc)

    if name in INVALID_REQUEST_EXCEPTION_NAMES:
        return invalid_request_cls(str(exc))
    if name in TRANSIENT_EXCEPTION_NAMES:
        return _transient_error(exc, retry_after, transient_cls)

    status_code = getattr(exc, 'status_code', None)
    if isinstance(status_code, int):
        if status_code == 429 or status_code in extra_transient_status_codes or status_code >= 500:
            return _transient_error(exc, retry_after, transient_cls)
        if 400 <= status_code < 500:
            return invalid_request_cls(str(exc))
    # Unrecognized failure (e.g. a raw connection error): assume transient so a
    # genuine blip gets retried rather than abandoning the document.
    return _transient_error(exc, retry_after, transient_cls)


def _transient_error(
    exc: Exception, retry_after: Optional[float], transient_cls: Type[RetryableError]
) -> RetryableError:
    error = transient_cls(str(exc))
    if retry_after is not None:
        error.retry_after_seconds = retry_after  # type: ignore[attr-defined]
        logger.info(
            'Request throttled; provider requested a %.1fs retry delay '
            '(the workflow RetryPolicy governs the actual backoff).',
            retry_after,
        )
    return error


def build_azure_client(
    *,
    endpoint: str,
    api_version: str,
    credential: Optional[Any],
    api_key: Optional[str],
    timeout: float,
    feature: str,
) -> Any:
    """Builds an `openai.AzureOpenAI` client, preferring Entra ID over an API key.

    Shared by `AzureOpenAIEmbedder` and `generation.AzureOpenAIChatClient` so
    the two authentication paths (and their dependency checks) stay in sync.

    Raises:
        OptionalDependencyError: `openai` is not installed, or a credential
            must be built and `azure-identity` is not installed.
    """
    if openai is None:
        raise OptionalDependencyError(package='openai', extra='rag', feature=feature)

    client_kwargs: dict[str, Any] = {
        'azure_endpoint': endpoint,
        'api_version': api_version,
        'timeout': timeout,
    }
    if api_key is not None:
        client_kwargs['api_key'] = api_key
    else:
        resolved_credential = credential
        if resolved_credential is None:
            if DefaultAzureCredential is None:
                raise OptionalDependencyError(
                    package='azure-identity', extra='rag-azure', feature=feature
                )
            resolved_credential = DefaultAzureCredential()
        if get_bearer_token_provider is None:
            raise OptionalDependencyError(
                package='azure-identity', extra='rag-azure', feature=feature
            )
        client_kwargs['azure_ad_token_provider'] = get_bearer_token_provider(
            resolved_credential, AAD_SCOPE
        )
    return openai.AzureOpenAI(**client_kwargs)


def _extract_retry_after(exc: Exception) -> Optional[float]:
    """Reads a `Retry-After` response header, in seconds, if the SDK exposes one."""
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', None)
    get_header = getattr(
        headers, 'get', None
    )  # dynamic: avoids a static .get() on a possibly-None headers
    value = get_header('retry-after') if callable(get_header) else None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
