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

# Query-time answer generation. Deliberately outside the durable ingestion
# path: nothing here runs inside a workflow activity or affects the
# pipeline's determinism/idempotency guarantees -- it's a plain synchronous
# call a retrieval-time reader (e.g. examples/rag/query_api.py) makes after
# `retrieval.ActiveVersionResolver.query(...)` returns matches. Not part of
# the spec's original interface sketch; added because the Azure-native
# sample's flagship path explicitly ends in a grounded, cited answer.

from __future__ import annotations

from typing import Any, Optional, Sequence

from dapr.ext.rag.embedding import _openai_common
from dapr.ext.rag.errors import InvalidGenerationRequestError, TransientGenerationError
from dapr.ext.rag.models import AnswerResult, Citation, QueryMatch

_AZURE_EXTRA_TRANSIENT_STATUS_CODES = frozenset({408})

_SYSTEM_PROMPT = (
    'You are a precise assistant that answers questions using only the numbered context '
    'passages provided. Cite passages by their bracketed number inline, e.g. [1]. If the '
    'context does not contain enough information to answer confidently, say so plainly '
    'rather than guessing.'
)


class AzureOpenAIChatClient:
    """Generates a grounded, cited answer from retrieved chunks via Azure OpenAI chat."""

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        api_version: str = _openai_common.DEFAULT_AZURE_API_VERSION,
        credential: Optional[Any] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        min_context_matches: int = 1,
        min_score: float = 0.0,
        client: Optional[Any] = None,
    ) -> None:
        """Initializes an AzureOpenAIChatClient.

        Args:
            endpoint: The Azure OpenAI resource endpoint.
            deployment: The chat-completion deployment name (may be a
                different deployment than the one `AzureOpenAIEmbedder` uses).
            api_version: The Azure OpenAI REST API version.
            credential: An `azure-identity` credential; defaults to
                `DefaultAzureCredential()` when neither this nor `api_key`
                is given.
            api_key: Optional API key, for development only.
            timeout: Per-request timeout, in seconds.
            min_context_matches: Minimum number of retrieved matches (after
                `min_score` filtering) required before attempting an answer;
                below this, `generate_answer` returns an insufficient-evidence
                result without calling the model at all.
            min_score: Matches scoring below this are treated as irrelevant
                context and excluded before both the `min_context_matches`
                check and the prompt itself.
            client: A pre-built `openai.AzureOpenAI` client (or any object
                exposing `.chat.completions.create(...)`) to use instead of
                constructing one -- bypasses the `openai`/`azure-identity`
                dependency checks, which is how tests exercise this class
                without either installed.
        """
        self._deployment = deployment
        self._min_context_matches = min_context_matches
        self._min_score = min_score
        self._client = client or _openai_common.build_azure_client(
            endpoint=endpoint,
            api_version=api_version,
            credential=credential,
            api_key=api_key,
            timeout=timeout,
            feature='AzureOpenAIChatClient',
        )

    def generate_answer(
        self,
        question: str,
        matches: Sequence[QueryMatch],
        *,
        index_version: str,
        workflow_instance_id: Optional[str] = None,
    ) -> AnswerResult:
        """Generates a grounded answer, or an insufficient-evidence result.

        Args:
            question: The user's question.
            matches: Retrieved chunks, e.g. from
                `retrieval.ActiveVersionResolver.query(...)`.
            index_version: The version `matches` was retrieved from, echoed
                back on the result for traceability.
            workflow_instance_id: Optional ingestion workflow instance ID to
                echo back, if the caller wants to correlate an answer with
                the run that produced its index.

        Returns:
            An `AnswerResult`. When there isn't enough relevant context,
            `sufficient_evidence` is `False` and `answer` is a plain refusal
            rather than a best-effort guess -- the model is not called at all
            in that case.

        Raises:
            TransientGenerationError: The chat-completion request failed
                transiently (throttling, timeout, provider-side 5xx).
            InvalidGenerationRequestError: The provider rejected the request
                as invalid.
        """
        relevant = [m for m in matches if m.score >= self._min_score]
        if len(relevant) < self._min_context_matches:
            return AnswerResult(
                answer=("I don't have enough indexed information to answer that confidently."),
                citations=(),
                index_version=index_version,
                sufficient_evidence=False,
                workflow_instance_id=workflow_instance_id,
            )

        context_block = '\n\n'.join(
            f'[{ordinal}] {match.content}' for ordinal, match in enumerate(relevant, start=1)
        )
        messages = [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': f'Context:\n{context_block}\n\nQuestion: {question}'},
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                temperature=0.0,
            )
        except Exception as exc:
            raise _openai_common.classify_error(
                exc,
                extra_transient_status_codes=_AZURE_EXTRA_TRANSIENT_STATUS_CODES,
                transient_cls=TransientGenerationError,
                invalid_request_cls=InvalidGenerationRequestError,
            ) from exc

        answer_text = response.choices[0].message.content or ''
        citations = tuple(
            Citation(
                title=str(match.metadata.get('source_name', match.document_id)),
                source_uri=str(
                    match.metadata.get('source_uri', match.metadata.get('source_document_id', ''))
                ),
                chunk_id=match.chunk_id,
                score=match.score,
            )
            for match in relevant
        )
        return AnswerResult(
            answer=answer_text,
            citations=citations,
            index_version=index_version,
            sufficient_evidence=True,
            workflow_instance_id=workflow_instance_id,
        )
