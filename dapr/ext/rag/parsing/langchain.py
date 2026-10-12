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

from __future__ import annotations

from typing import Any, Iterable

from dapr.ext.rag.errors import OptionalDependencyError
from dapr.ext.rag.models import Document

try:
    from langchain_core.documents import Document as _LangchainDocument
except ImportError:  # pragma: no cover - exercised only without langchain-core installed
    _LangchainDocument = None


def to_langchain_documents(documents: Iterable[Document]) -> list[Any]:
    """Converts this package's `Document`s into LangChain `Document`s.

    Args:
        documents: `Document`s to convert.

    Returns:
        A list of `langchain_core.documents.Document`, one per input.

    Raises:
        OptionalDependencyError: `langchain-core` is not installed.
    """
    if _LangchainDocument is None:
        raise OptionalDependencyError(
            package='langchain-core', extra='rag-langchain', feature='to_langchain_documents'
        )
    return [
        _LangchainDocument(page_content=doc.page_content, metadata=dict(doc.metadata))
        for doc in documents
    ]


def from_langchain_documents(documents: Iterable[Any]) -> list[Document]:
    """Converts LangChain `Document`s (or any `page_content`/`metadata` object) back.

    Duck-typed on `.page_content` / `.metadata` rather than importing
    `langchain_core`, so callers who already have LangChain `Document`
    instances can convert them without this package requiring LangChain to be
    installed for this direction.

    Args:
        documents: Objects exposing `.page_content: str` and `.metadata: dict`.

    Returns:
        A list of this package's `Document`, one per input, with page content
        and metadata preserved.
    """
    return [
        Document(page_content=doc.page_content, metadata=dict(doc.metadata)) for doc in documents
    ]
