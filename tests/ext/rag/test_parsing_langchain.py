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

import unittest
from unittest import mock

from dapr.ext.rag.errors import OptionalDependencyError
from dapr.ext.rag.models import Document
from dapr.ext.rag.parsing.langchain import from_langchain_documents, to_langchain_documents


class _DuckTypedDocument:
    """A minimal page_content/metadata object -- not a real LangChain Document."""

    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class ToLangchainDocumentsTest(unittest.TestCase):
    def test_converts_preserving_content_and_metadata(self):
        documents = [Document(page_content='hello', metadata={'page_number': 1})]
        converted = to_langchain_documents(documents)
        self.assertEqual(len(converted), 1)
        self.assertEqual(converted[0].page_content, 'hello')
        self.assertEqual(converted[0].metadata, {'page_number': 1})

    def test_converts_multiple_documents_preserving_order(self):
        documents = [Document(page_content=f'doc-{i}') for i in range(3)]
        converted = to_langchain_documents(documents)
        self.assertEqual([d.page_content for d in converted], ['doc-0', 'doc-1', 'doc-2'])

    def test_raises_optional_dependency_error_when_langchain_core_is_missing(self):
        with mock.patch('dapr.ext.rag.parsing.langchain._LangchainDocument', None):
            with self.assertRaises(OptionalDependencyError):
                to_langchain_documents([Document(page_content='hello')])


class FromLangchainDocumentsTest(unittest.TestCase):
    def test_converts_real_langchain_documents(self):
        from langchain_core.documents import Document as LangchainDocument

        lc_docs = [LangchainDocument(page_content='hello', metadata={'source': 'a.txt'})]
        converted = from_langchain_documents(lc_docs)
        self.assertEqual(converted, [Document(page_content='hello', metadata={'source': 'a.txt'})])

    def test_converts_duck_typed_documents_without_requiring_langchain(self):
        # No `langchain_core` import happens on this path -- see from_langchain_documents'
        # docstring -- so this must work even if langchain-core were uninstalled.
        duck_docs = [_DuckTypedDocument(page_content='hello', metadata={'a': 1})]
        converted = from_langchain_documents(duck_docs)
        self.assertEqual(converted, [Document(page_content='hello', metadata={'a': 1})])

    def test_round_trips_through_to_and_from(self):
        original = [Document(page_content='hello', metadata={'k': 'v'})]
        round_tripped = from_langchain_documents(to_langchain_documents(original))
        self.assertEqual(round_tripped, original)


if __name__ == '__main__':
    unittest.main()
