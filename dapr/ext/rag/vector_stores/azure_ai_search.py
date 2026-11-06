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

# One physical Azure AI Search index per pipeline version (`{index_base_name}
# -{version}`), routed through a stable alias (`{index_base_name}-active` by
# default) that `activate_version` atomically repoints -- see that method's
# docstring for the read-check-write-poll sequence the spec requires. Unlike
# pgvector/Pinecone, "version" here is *not* a column/namespace inside one
# always-queryable index; it names a whole separate physical index, so the
# Dapr-state `ActivationRecord` (state.py) alone is not enough to route
# Azure AI Search traffic -- the alias is the actual routing mechanism, and
# this class participates in the two-step activation sequence documented on
# `VectorIndex.activate_version`.
#
# No local/offline emulator exists for Azure AI Search (unlike LocalStack/
# Azurite for S3/Blob), so this class is tested only via dependency injection
# (`index_client=`/`search_client_factory=`) against fakes -- see
# dapr/ext/rag/AGENTS.md and the completion report for what that does and
# does not verify.

from __future__ import annotations

import time
from typing import Any, Callable, Iterable, Iterator, Optional, TypeVar

from dapr.ext.rag.errors import (
    OptionalDependencyError,
    RagError,
    TransientVectorStoreError,
    VectorStoreError,
)
from dapr.ext.rag.models import QueryMatch, UpsertResult, ValidationResult, VectorRecord
from dapr.ext.rag.vector_stores.base import VectorIndex

# See dapr/ext/rag/AGENTS.md for why the optional-dependency guard lives here,
# per adapter module, rather than once in dapr/ext/rag/__init__.py.
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        HnswParameters,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )
    from azure.search.documents.models import VectorizedQuery
except ImportError:  # pragma: no cover - exercised only without azure-search-documents installed
    AzureKeyCredential = None  # type: ignore[assignment,misc]
    SearchClient = SearchIndexClient = None  # type: ignore[assignment,misc]
    HnswAlgorithmConfiguration = HnswParameters = SearchableField = None  # type: ignore[assignment,misc]
    SearchField = SearchFieldDataType = SearchIndex = None  # type: ignore[assignment,misc]
    SemanticConfiguration = SemanticField = SemanticPrioritizedFields = None  # type: ignore[assignment,misc]
    SemanticSearch = SimpleField = VectorSearch = VectorSearchProfile = None  # type: ignore[assignment,misc]
    VectorizedQuery = None  # type: ignore[assignment,misc]

try:
    from azure.identity import DefaultAzureCredential
except ImportError:  # pragma: no cover - exercised only without azure-identity installed
    DefaultAzureCredential = None  # type: ignore[assignment,misc]

try:
    import httpx
except ImportError:  # pragma: no cover - exercised only without httpx installed
    httpx = None  # type: ignore[assignment]

_VECTOR_FIELD_NAME = 'content_vector'
_VECTOR_PROFILE_NAME = 'rag-vector-profile'
_HNSW_ALGORITHM_NAME = 'rag-hnsw'

# Index aliases were briefly a beta SDK feature (11.4.0b1) but were removed
# before the stable 11.4.0 release and have not been restored in any
# azure-search-documents version since (verified against the SDK's own
# CHANGELOG.md on 2026-09-10) -- SearchIndexClient has no alias method at all.
# The REST API itself does support them, so activate_version talks to it
# directly instead. Verified against Microsoft's REST API reference
# (searchservice.aliases.createorupdate) on 2026-09-10.
#
# Foundry IQ knowledge sources are the same story: `SearchIndexKnowledgeSource`/
# `SearchIndexKnowledgeSourceParameters` do not exist in azure-search-documents
# 11.6.0 (confirmed by introspecting the installed package on 2026-09-10) even
# though Microsoft's own docs illustrate them as SDK calls -- the feature is
# GA at the REST layer (2026-04-01) but not yet wrapped by this SDK version.
# register_foundry_iq_knowledge_source below talks to the REST API directly,
# reusing the same transport/credential/headers as the alias calls (same
# management-plane surface, same auth) -- verified against Microsoft's REST
# API reference (searchservice.knowledge-sources.create-or-update) on
# 2026-09-10. Named _MANAGEMENT_* (not _ALIAS_*) since both features share it.
_MANAGEMENT_API_VERSION = '2026-04-01'
_MANAGEMENT_REQUEST_TIMEOUT_SECONDS = 30.0

# Classified by exception *name*, not `isinstance` against the azure-core
# classes above: when azure-core isn't installed, every name in that
# try/except aliases to the same `Exception`, which would make an isinstance
# check match (and thus misclassify) anything.
_NOT_FOUND_EXCEPTION_NAMES = frozenset({'ResourceNotFoundError'})
_TRANSIENT_EXCEPTION_NAMES = frozenset(
    {
        'ServiceRequestError',
        'ServiceResponseError',
        # httpx's own transient exceptions, from the alias REST calls below.
        'ConnectError',
        'ConnectTimeout',
        'ReadTimeout',
        'WriteTimeout',
        'PoolTimeout',
        'TimeoutException',
    }
)


def _is_not_found(exc: Exception) -> bool:
    return type(exc).__name__ in _NOT_FOUND_EXCEPTION_NAMES


# Every schema field except the vector -- the default `select` for query(),
# so the (large) vector is never returned unless a caller explicitly asks
# for it via `include_vector=True`.
_DEFAULT_SELECT_FIELDS = [
    'id',
    'content',
    'title',
    'source_uri',
    'source_provider',
    'source_document_id',
    'source_etag',
    'source_version',
    'source_content_hash',
    'document_ordinal',
    'chunk_ordinal',
    'chunk_content_hash',
    'content_type',
    'pipeline_id',
    'pipeline_version',
    'workflow_instance_id',
    'parser_version',
    'splitter_version',
    'embedding_provider',
    'embedding_model',
    'ingested_at',
    'tenant_id',
    'authorization_groups',
]

T = TypeVar('T')


class AzureAISearchVectorStore(VectorIndex):
    """An Azure AI Search-backed `VectorIndex`, one physical index per version.

    Supports pure-vector, pure-keyword, and hybrid (default) retrieval, with
    optional semantic ranking when `semantic_configuration_name` is set and
    the Search service's tier/configuration supports it.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        index_base_name: str,
        alias_name: Optional[str] = None,
        credential: Optional[Any] = None,
        api_key: Optional[str] = None,
        vector_dimensions: Optional[int] = None,
        semantic_configuration_name: Optional[str] = None,
        batch_size: int = 100,
        max_batch_retries: int = 3,
        alias_poll_attempts: int = 5,
        alias_poll_interval_seconds: float = 1.0,
        index_client: Optional[Any] = None,
        search_client_factory: Optional[Callable[[str], Any]] = None,
        alias_transport: Optional[Any] = None,
    ) -> None:
        """Initializes an AzureAISearchVectorStore.

        Args:
            endpoint: The Azure AI Search service endpoint, e.g.
                `https://my-search.search.windows.net`. Always required, even
                when `index_client`/`search_client_factory` are injected: the
                alias REST calls below (see the module comment on why they
                aren't SDK calls) need it regardless.
            index_base_name: The logical index name; each version gets its
                own physical index `{index_base_name}-{version}`.
            alias_name: The stable alias query traffic should read through.
                Defaults to `{index_base_name}-active`.
            credential: An `azure-identity` credential for Microsoft Entra ID
                authentication. Defaults to `DefaultAzureCredential()` when
                neither this nor `api_key` is given.
            api_key: Optional API key, for development only. Never logged.
            vector_dimensions: The embedding vector width, used to create a
                new physical index's vector field. Inferred from the first
                batch passed to `upsert` when omitted.
            semantic_configuration_name: Enables semantic ranking with this
                configuration name when the Search service tier supports it;
                `None` disables it.
            batch_size: Records per `merge_or_upload_documents` call.
            max_batch_retries: How many times to retry just the batch
                members Azure AI Search reported as failed before raising.
            alias_poll_attempts: How many times `activate_version` re-checks
                the alias mapping after switching it, waiting for the
                propagation Azure AI Search documents for alias updates.
            alias_poll_interval_seconds: Delay between alias-mapping checks.
            index_client: A pre-built `SearchIndexClient` (index administration)
                to use instead of constructing one -- bypasses the
                `azure-search-documents` dependency check, which is how tests
                exercise index/document operations without it installed.
                Requires `search_client_factory` too.
            search_client_factory: A callable `(index_name) -> SearchClient`
                (document operations), used instead of constructing one per
                physical index -- required when `index_client` is given.
            alias_transport: An object exposing `.get(url, headers=...)` /
                `.put(url, json=..., headers=...)` returning a
                `.status_code`/`.text`/`.json()`-shaped response (i.e. an
                `httpx.Client`-compatible interface), used for alias REST
                calls instead of constructing a real `httpx.Client` --
                bypasses the `httpx` dependency check, which is how tests
                exercise `activate_version` without it installed.

        Raises:
            OptionalDependencyError: `azure-search-documents` is not
                installed and no `index_client` was given; `httpx` is not
                installed and no `alias_transport` was given; or
                `azure-identity` is needed to build the default credential
                and is not installed.
            ValueError: `index_client` was given without `search_client_factory`.
        """
        self._endpoint = endpoint.rstrip('/')
        self._index_base_name = index_base_name
        self._alias_name = alias_name or f'{index_base_name}-active'
        self._vector_dimensions = vector_dimensions
        self._semantic_configuration_name = semantic_configuration_name
        self._batch_size = batch_size
        self._max_batch_retries = max_batch_retries
        self._alias_poll_attempts = alias_poll_attempts
        self._alias_poll_interval_seconds = alias_poll_interval_seconds
        self._ensured_indexes: set[str] = set()
        self._search_clients: dict[str, Any] = {}

        if index_client is not None and search_client_factory is None:
            raise ValueError('search_client_factory is required when index_client is injected.')
        if index_client is None and (SearchIndexClient is None or SearchClient is None):
            raise OptionalDependencyError(
                package='azure-search-documents',
                extra='rag-azure-search',
                feature='AzureAISearchVectorStore',
            )

        # A credential is only actually needed if *something* below isn't fully
        # dependency-injected; when both index_client and alias_transport are
        # given (the unit-test path), no azure-identity dependency is touched at all.
        resolved_credential = None
        if index_client is None or alias_transport is None:
            resolved_credential = _resolve_credential(credential, api_key)

        if index_client is not None:
            # The guard clause above already rejected index_client without
            # search_client_factory; this repeats that fact for mypy.
            assert search_client_factory is not None
            self._index_client = index_client
            self._search_client_factory = search_client_factory
        else:
            # index_client is None => the `if` above always resolved a credential.
            assert resolved_credential is not None
            self._index_client = SearchIndexClient(
                endpoint=endpoint, credential=resolved_credential
            )
            self._search_client_factory = lambda index_name: SearchClient(
                endpoint=endpoint, index_name=index_name, credential=resolved_credential
            )

        self._alias_credential = resolved_credential
        if alias_transport is not None:
            self._alias_transport = alias_transport
        else:
            if httpx is None:
                raise OptionalDependencyError(
                    package='httpx', extra='rag-azure-search', feature='AzureAISearchVectorStore'
                )
            self._alias_transport = httpx.Client(timeout=_MANAGEMENT_REQUEST_TIMEOUT_SECONDS)

    @property
    def target_index_name(self) -> str:
        return self._index_base_name

    @property
    def alias_name(self) -> str:
        """The stable alias query traffic reads through."""
        return self._alias_name

    @property
    def store_type(self) -> str:
        return 'azure-ai-search'

    def upsert(self, records: Iterable[VectorRecord], version: str) -> UpsertResult:
        materialized = list(records)
        if not materialized:
            return UpsertResult(upserted_count=0, version=version)

        index_name = self._index_name_for(version)
        dimensions = self._vector_dimensions or len(materialized[0].embedding)
        self._ensure_index(index_name, dimensions)
        search_client = self._search_client(index_name)

        upserted_count = 0
        for batch in _batched(materialized, self._batch_size):
            documents = [_to_search_document(record) for record in batch]
            upserted_count += self._upload_with_retry(search_client, documents)
        return UpsertResult(upserted_count=upserted_count, version=version)

    def delete_document(self, document_id: str, version: str) -> None:
        index_name = self._index_name_for(version)
        search_client = self._search_client(index_name)
        try:
            matches = search_client.search(
                search_text='*',
                filter=f"source_document_id eq '{_escape_odata_string(document_id)}'",
                select=['id'],
                top=1000,
            )
            keys = [match['id'] for match in matches]
            if keys:
                search_client.delete_documents(documents=[{'id': key} for key in keys])
        except Exception as exc:
            raise self._classify(exc) from exc

    def validate_version(self, version: str) -> ValidationResult:
        index_name = self._index_name_for(version)
        try:
            self._index_client.get_index(index_name)
        except Exception as exc:
            if _is_not_found(exc):
                return ValidationResult(
                    valid=False,
                    version=version,
                    actual_chunk_count=0,
                    details=f'Index {index_name!r} does not exist.',
                )
            raise self._classify(exc) from exc

        try:
            count = self._search_client(index_name).get_document_count()
        except Exception as exc:
            raise self._classify(exc) from exc

        return ValidationResult(
            valid=count > 0,
            version=version,
            actual_chunk_count=count,
            details=f'{count} chunk(s) in index {index_name!r}.',
        )

    def activate_version(self, version: str, *, previous_version: Optional[str]) -> None:
        """Atomically repoints the alias to this version's physical index.

        Retry-safe: reads the current alias mapping first and returns
        immediately if it already points to the target index (an activity
        retry after a partial failure, or a repeated activation, is then a
        no-op). Otherwise switches the alias and polls until the new mapping
        is observable, matching Azure AI Search's documented alias
        propagation delay -- never deletes or repurposes `previous_version`'s
        index.

        Raises:
            TransientVectorStoreError: The alias switch failed transiently,
                or didn't become observable within `alias_poll_attempts`.
            VectorStoreError: The alias switch failed non-transiently.
        """
        new_index_name = self._index_name_for(version)
        if self._alias_indexes() == [new_index_name]:
            return  # already correct: idempotent no-op

        self._put_alias(new_index_name)

        for _attempt in range(self._alias_poll_attempts):
            if self._alias_indexes() == [new_index_name]:
                return
            time.sleep(self._alias_poll_interval_seconds)

        raise TransientVectorStoreError(
            f'Alias {self._alias_name!r} did not observably switch to {new_index_name!r} after '
            f'{self._alias_poll_attempts} check(s); a retry will re-check rather than switch again.'
        )

    def register_foundry_iq_knowledge_source(
        self,
        version: str,
        *,
        name: str,
        description: Optional[str] = None,
        source_data_fields: Optional[list[str]] = None,
        search_fields: Optional[list[str]] = None,
    ) -> None:
        """Registers (or updates) a Foundry IQ search-index knowledge source for `version`.

        Opt-in and separate from this store's own retrieval path -- see
        `docs/rag/foundry-iq.md` for the full rationale and the rule this
        follows if a caller ever wires this up. Not called from anywhere in
        `dapr.ext.rag` by default; a caller invokes this explicitly (e.g. from
        a workflow activity chained strictly after `activate_version`
        succeeds for `version`, as the doc specifies) when they want this
        version's index registered with Foundry IQ.

        Deliberately targets `{index_base_name}-{version}` (the concrete
        physical index), never the alias: whether a knowledge source resolves
        an alias dynamically or binds to whatever index it pointed at when
        created is undocumented, so this method assumes the more dangerous
        case (it binds once) and always re-points the knowledge source
        explicitly -- the same reasoning `activate_version` applies to the
        alias itself.

        Idempotent: a no-op if the knowledge source already targets this
        exact index and semantic configuration.

        Raises:
            VectorStoreError: This store has no `semantic_configuration_name`
                configured -- required on every search index knowledge source
                by the `2026-04-01` REST API this method targets -- or the
                registration request failed non-transiently.
            TransientVectorStoreError: The registration request failed
                transiently.
        """
        if not self._semantic_configuration_name:
            raise VectorStoreError(
                'register_foundry_iq_knowledge_source requires semantic_configuration_name to '
                'be set on this AzureAISearchVectorStore -- required by every search index '
                'knowledge source on the 2026-04-01 REST API this method targets.'
            )
        target_index_name = self._index_name_for(version)
        existing = self._get_knowledge_source(name)
        existing_params = (existing or {}).get('searchIndexParameters') or {}
        already_correct = (
            existing is not None
            and existing_params.get('searchIndexName') == target_index_name
            and existing_params.get('semanticConfigurationName')
            == self._semantic_configuration_name
        )
        if already_correct:
            return  # idempotent no-op

        self._put_knowledge_source(
            name,
            {
                'name': name,
                'kind': 'searchIndex',
                'description': description,
                'searchIndexParameters': {
                    'searchIndexName': target_index_name,
                    'semanticConfigurationName': self._semantic_configuration_name,
                    'sourceDataFields': [{'name': field} for field in (source_data_fields or [])],
                    'searchFields': [{'name': field} for field in (search_fields or [])],
                },
            },
        )

    def query(
        self,
        embedding: Iterable[float],
        version: str,
        *,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
        query_text: Optional[str] = None,
        mode: str = 'hybrid',
        include_vector: bool = False,
    ) -> list[QueryMatch]:
        """Runs a vector, keyword, or hybrid (default) search.

        Args:
            mode: `'vector'`, `'keyword'`, or `'hybrid'` (vector + keyword,
                merged by Azure AI Search -- the default, per this store's
                design: hybrid retrieval is what the flagship sample uses).
            include_vector: When `True`, includes the (large) embedding
                vector field in results. Excluded by default.
        """
        index_name = self._index_name_for(version)
        search_client = self._search_client(index_name)

        search_kwargs: dict[str, Any] = {'top': top_k}
        if not include_vector:
            search_kwargs['select'] = _DEFAULT_SELECT_FIELDS
        if metadata_filter:
            search_kwargs['filter'] = _build_odata_filter(metadata_filter)
        if mode in ('vector', 'hybrid'):
            search_kwargs['vector_queries'] = [
                VectorizedQuery(
                    vector=list(embedding), k_nearest_neighbors=top_k, fields=_VECTOR_FIELD_NAME
                )
            ]
        if mode in ('keyword', 'hybrid'):
            search_kwargs['search_text'] = query_text or '*'
        if self._semantic_configuration_name and mode != 'vector':
            search_kwargs['query_type'] = 'semantic'
            search_kwargs['semantic_configuration_name'] = self._semantic_configuration_name

        try:
            results = search_client.search(**search_kwargs)
        except Exception as exc:
            raise self._classify(exc) from exc

        return [
            _to_query_match(result, semantic=bool(self._semantic_configuration_name))
            for result in results
        ]

    def close(self) -> None:
        for client in (self._index_client, self._alias_transport, *self._search_clients.values()):
            close = getattr(client, 'close', None)
            if callable(close):
                close()

    # -- internal helpers ---------------------------------------------------

    def _index_name_for(self, version: str) -> str:
        return f'{self._index_base_name}-{version}'

    def _search_client(self, index_name: str) -> Any:
        client = self._search_clients.get(index_name)
        if client is None:
            client = self._search_client_factory(index_name)
            self._search_clients[index_name] = client
        return client

    def _alias_indexes(self) -> list[str]:
        """Returns the alias's current target index names, or `[]` if it doesn't exist yet.

        A direct REST call, not an SDK method -- see the module comment on
        why `SearchIndexClient` has no alias support to call instead.
        """
        try:
            response = self._alias_transport.get(self._alias_url(), headers=self._alias_headers())
        except Exception as exc:
            raise self._classify(exc) from exc
        if response.status_code == 404:
            return []
        _raise_for_alias_response(response)
        return list(response.json().get('indexes', []))

    def _put_alias(self, index_name: str) -> None:
        try:
            response = self._alias_transport.put(
                self._alias_url(),
                headers={**self._alias_headers(), 'Content-Type': 'application/json'},
                json={'name': self._alias_name, 'indexes': [index_name]},
            )
        except Exception as exc:
            raise self._classify(exc) from exc
        _raise_for_alias_response(response)

    def _alias_url(self) -> str:
        return (
            f"{self._endpoint}/aliases('{self._alias_name}')?api-version={_MANAGEMENT_API_VERSION}"
        )

    def _get_knowledge_source(self, name: str) -> Optional[dict[str, Any]]:
        try:
            response = self._alias_transport.get(
                self._knowledge_source_url(name), headers=self._alias_headers()
            )
        except Exception as exc:
            raise self._classify(exc) from exc
        if response.status_code == 404:
            return None
        _raise_for_alias_response(response)
        return dict(response.json())

    def _put_knowledge_source(self, name: str, body: dict[str, Any]) -> None:
        try:
            response = self._alias_transport.put(
                self._knowledge_source_url(name),
                headers={**self._alias_headers(), 'Content-Type': 'application/json'},
                json=body,
            )
        except Exception as exc:
            raise self._classify(exc) from exc
        _raise_for_alias_response(response)

    def _knowledge_source_url(self, name: str) -> str:
        return f"{self._endpoint}/knowledgesources('{name}')?api-version={_MANAGEMENT_API_VERSION}"

    def _alias_headers(self) -> dict[str, str]:
        """Auth headers for this store's REST management calls -- aliases and Foundry IQ
        knowledge sources alike (both are otherwise-unsupported-by-the-SDK REST calls
        against the same management plane, using the same credential)."""
        api_key = getattr(self._alias_credential, 'key', None)
        if api_key is not None:
            return {'api-key': api_key}
        if self._alias_credential is not None:
            token = self._alias_credential.get_token('https://search.azure.com/.default')
            return {'Authorization': f'Bearer {token.token}'}
        return {}

    def _ensure_index(self, index_name: str, dimensions: int) -> None:
        if index_name in self._ensured_indexes:
            return
        try:
            existing = self._index_client.get_index(index_name)
        except Exception as exc:
            if not _is_not_found(exc):
                raise self._classify(exc) from exc
            existing = None

        try:
            if existing is None:
                schema = _build_index_schema(
                    index_name, dimensions, self._semantic_configuration_name
                )
                self._index_client.create_index(schema)
            else:
                _validate_existing_schema(existing, dimensions)
        except Exception as exc:
            raise self._classify(exc) from exc
        self._ensured_indexes.add(index_name)

    def _upload_with_retry(self, search_client: Any, documents: list[dict[str, Any]]) -> int:
        pending = documents
        succeeded_count = 0
        for attempt in range(self._max_batch_retries + 1):
            try:
                results = search_client.merge_or_upload_documents(documents=pending)
            except Exception as exc:
                raise self._classify(exc) from exc

            failed_keys = {result.key for result in results if not result.succeeded}
            succeeded_count += len(pending) - len(failed_keys)
            if not failed_keys:
                return succeeded_count
            if attempt == self._max_batch_retries:
                raise TransientVectorStoreError(
                    f'{len(failed_keys)} document(s) failed to index after '
                    f'{self._max_batch_retries} retry attempt(s): {sorted(failed_keys)}'
                )
            pending = [
                doc for doc in pending if doc['id'] in failed_keys
            ]  # retry only failed members
        return succeeded_count  # unreachable: the loop above always returns or raises

    @staticmethod
    def _classify(exc: Exception) -> RagError:
        if type(exc).__name__ in _TRANSIENT_EXCEPTION_NAMES:
            return TransientVectorStoreError(str(exc))
        status_code = getattr(exc, 'status_code', None)
        if isinstance(status_code, int) and (status_code == 429 or status_code >= 500):
            return TransientVectorStoreError(str(exc))
        return VectorStoreError(str(exc))


def _raise_for_alias_response(response: Any) -> None:
    """Raises a classified error for a non-2xx alias REST response.

    A separate check from `AzureAISearchVectorStore._classify` (which
    classifies *exceptions*): httpx doesn't raise for a non-2xx status by
    itself, so an HTTP-level failure surfaces as a normal response object,
    not an exception, unless explicitly checked here.
    """
    if response.status_code < 400:
        return
    message = f'Alias request failed with status {response.status_code}: {response.text}'
    if response.status_code == 429 or response.status_code >= 500:
        raise TransientVectorStoreError(message)
    raise VectorStoreError(message)


def _resolve_credential(credential: Optional[Any], api_key: Optional[str]) -> Any:
    if api_key is not None:
        if AzureKeyCredential is None:
            raise OptionalDependencyError(
                package='azure-search-documents',
                extra='rag-azure-search',
                feature='AzureAISearchVectorStore',
            )
        return AzureKeyCredential(api_key)
    if credential is not None:
        return credential
    if DefaultAzureCredential is None:
        raise OptionalDependencyError(
            package='azure-identity', extra='rag-azure', feature='AzureAISearchVectorStore'
        )
    return DefaultAzureCredential()


def _build_index_schema(
    index_name: str, dimensions: int, semantic_configuration_name: Optional[str]
) -> Any:
    if SimpleField is None:
        # Reachable even with index_client/search_client_factory injected: DI bypasses
        # constructing the *clients*, not the schema *model* classes used here.
        raise OptionalDependencyError(
            package='azure-search-documents',
            extra='rag-azure-search',
            feature='AzureAISearchVectorStore',
        )
    fields = [
        SimpleField(name='id', type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name='content', type=SearchFieldDataType.String),
        SearchField(
            name=_VECTOR_FIELD_NAME,
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name=_VECTOR_PROFILE_NAME,
        ),
        SearchableField(
            name='title', type=SearchFieldDataType.String, filterable=True, sortable=True
        ),
        SimpleField(name='source_uri', type=SearchFieldDataType.String),
        SimpleField(name='source_provider', type=SearchFieldDataType.String, filterable=True),
        SimpleField(name='source_document_id', type=SearchFieldDataType.String, filterable=True),
        SimpleField(name='source_etag', type=SearchFieldDataType.String),
        SimpleField(name='source_version', type=SearchFieldDataType.String),
        SimpleField(name='source_content_hash', type=SearchFieldDataType.String),
        SimpleField(
            name='document_ordinal', type=SearchFieldDataType.Int32, filterable=True, sortable=True
        ),
        SimpleField(
            name='chunk_ordinal', type=SearchFieldDataType.Int32, filterable=True, sortable=True
        ),
        SimpleField(name='chunk_content_hash', type=SearchFieldDataType.String),
        SimpleField(name='content_type', type=SearchFieldDataType.String, filterable=True),
        SimpleField(name='pipeline_id', type=SearchFieldDataType.String, filterable=True),
        SimpleField(name='pipeline_version', type=SearchFieldDataType.String, filterable=True),
        SimpleField(name='workflow_instance_id', type=SearchFieldDataType.String, filterable=True),
        # "*_version" (matching the spec's schema field names) holds a config
        # *hash*, not a semantic version number -- see fingerprints.py.
        SimpleField(name='parser_version', type=SearchFieldDataType.String),
        SimpleField(name='splitter_version', type=SearchFieldDataType.String),
        SimpleField(name='embedding_provider', type=SearchFieldDataType.String, filterable=True),
        SimpleField(name='embedding_model', type=SearchFieldDataType.String, filterable=True),
        SimpleField(
            name='ingested_at',
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
        # Multi-tenancy pass-through: unset unless a caller's own Document/Chunk
        # metadata populates them -- see dapr/ext/rag/AGENTS.md's limitations.
        SimpleField(name='tenant_id', type=SearchFieldDataType.String, filterable=True),
        SimpleField(
            name='authorization_groups',
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=_HNSW_ALGORITHM_NAME,
                parameters=HnswParameters(m=4, ef_construction=400, ef_search=500, metric='cosine'),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=_VECTOR_PROFILE_NAME, algorithm_configuration_name=_HNSW_ALGORITHM_NAME
            )
        ],
    )
    semantic_search = None
    if semantic_configuration_name:
        semantic_search = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=semantic_configuration_name,
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name='title'),
                        content_fields=[SemanticField(field_name='content')],
                    ),
                )
            ]
        )
    return SearchIndex(
        name=index_name, fields=fields, vector_search=vector_search, semantic_search=semantic_search
    )


def _validate_existing_schema(existing_index: Any, expected_dimensions: int) -> None:
    vector_field = next((f for f in existing_index.fields if f.name == _VECTOR_FIELD_NAME), None)
    actual_dimensions = getattr(vector_field, 'vector_search_dimensions', None)
    if actual_dimensions is not None and actual_dimensions != expected_dimensions:
        raise VectorStoreError(
            f'Index {existing_index.name!r} already exists with vector dimensions '
            f'{actual_dimensions}, but this pipeline is configured for {expected_dimensions}. '
            'Use a different index_base_name or version rather than reusing a mismatched index.'
        )


def _to_search_document(record: VectorRecord) -> dict[str, Any]:
    metadata = record.metadata
    document = {
        'id': record.chunk_id,
        'content': record.content,
        _VECTOR_FIELD_NAME: list(record.embedding),
        'title': metadata.get('source_name'),
        'source_uri': metadata.get('source_uri'),
        'source_provider': metadata.get('source_provider'),
        'source_document_id': record.document_id,
        'source_etag': metadata.get('source_etag'),
        'source_version': metadata.get('source_version_id'),
        'source_content_hash': metadata.get('source_content_hash'),
        'document_ordinal': metadata.get('document_ordinal'),
        'chunk_ordinal': metadata.get('chunk_ordinal'),
        'chunk_content_hash': metadata.get('chunk_content_hash'),
        'content_type': metadata.get('source_content_type'),
        'pipeline_id': metadata.get('pipeline_id'),
        'pipeline_version': metadata.get('target_version'),
        'workflow_instance_id': metadata.get('workflow_instance_id'),
        'parser_version': metadata.get('parser_config_hash'),
        'splitter_version': metadata.get('splitter_config_hash'),
        'embedding_provider': metadata.get('embedding_provider'),
        'embedding_model': metadata.get('embedding_model'),
        'ingested_at': metadata.get('ingested_at'),
        'tenant_id': metadata.get('tenant_id'),
        'authorization_groups': metadata.get('authorization_groups') or [],
    }
    return {key: value for key, value in document.items() if value is not None}


def _to_query_match(result: Any, *, semantic: bool) -> QueryMatch:
    fields = dict(result)
    score = fields.pop('@search.score', 0.0)
    if semantic:
        score = fields.pop('@search.reranker_score', None) or score
    for key in list(fields):
        if key.startswith('@search.'):
            fields.pop(key)
    chunk_id = fields.pop('id', '')
    content = fields.pop('content', '') or ''
    document_id = fields.get('source_document_id', '') or ''
    return QueryMatch(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        score=float(score),
        metadata=fields,
    )


def _build_odata_filter(metadata_filter: dict[str, Any]) -> str:
    clauses = []
    for field, value in metadata_filter.items():
        if isinstance(value, str):
            clauses.append(f"{field} eq '{_escape_odata_string(value)}'")
        elif isinstance(value, bool):
            clauses.append(f'{field} eq {"true" if value else "false"}')
        elif isinstance(value, (int, float)):
            clauses.append(f'{field} eq {value}')
        else:
            raise ValueError(
                f'Unsupported metadata_filter value type for {field!r}: {type(value).__name__}'
            )
    return ' and '.join(clauses)


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _batched(items: list[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
