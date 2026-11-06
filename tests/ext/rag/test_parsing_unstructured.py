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
from types import SimpleNamespace
from unittest import mock

from dapr.ext.rag.errors import (
    DocumentParseError,
    OptionalDependencyError,
    UnsupportedDocumentError,
)
from dapr.ext.rag.models import SourceDocument, SourceMetadata, SourceProvider
from dapr.ext.rag.parsing.unstructured import UnstructuredParser


def _element(text, page_number=None):
    return SimpleNamespace(text=text, metadata=SimpleNamespace(page_number=page_number))


def _doc(name='a.txt', content_type=None):
    return SourceDocument(
        document_id=f's3://bucket/{name}',
        provider=SourceProvider.S3,
        uri=f's3://bucket/{name}',
        name=name,
        metadata=SourceMetadata(content_type=content_type),
    )


class UnstructuredParserConstructionTest(unittest.TestCase):
    def test_parser_type_is_stable(self):
        self.assertEqual(
            UnstructuredParser(partition_fn=lambda **_: []).parser_type, 'unstructured'
        )

    def test_config_reflects_strategy_and_languages(self):
        parser = UnstructuredParser(
            strategy='hi_res', languages=['eng'], partition_fn=lambda **_: []
        )
        self.assertEqual(parser.config(), {'strategy': 'hi_res', 'languages': ('eng',)})

    def test_raises_optional_dependency_error_without_unstructured_or_partition_fn(self):
        with mock.patch('dapr.ext.rag.parsing.unstructured._default_partition', None):
            parser = UnstructuredParser()
            with self.assertRaises(OptionalDependencyError):
                parser.parse(b'hello', _doc())


class UnstructuredParserParseTest(unittest.TestCase):
    def test_unsupported_extension_raises_without_calling_partition(self):
        partition_fn = mock.Mock()
        parser = UnstructuredParser(partition_fn=partition_fn)
        with self.assertRaises(UnsupportedDocumentError):
            parser.parse(b'binary', _doc(name='a.exe'))
        partition_fn.assert_not_called()

    def test_groups_elements_by_page_number(self):
        elements = [
            _element('Title', page_number=1),
            _element('Body text on page 1', page_number=1),
            _element('Body text on page 2', page_number=2),
        ]
        parser = UnstructuredParser(partition_fn=lambda **_: elements)
        documents = parser.parse(b'%PDF-1.4...', _doc(name='a.pdf'))
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].page_content, 'Title\n\nBody text on page 1')
        self.assertEqual(documents[0].metadata['page_number'], 1)
        self.assertEqual(documents[1].page_content, 'Body text on page 2')
        self.assertEqual(documents[1].metadata['page_number'], 2)

    def test_documents_without_pages_collapse_to_a_single_document(self):
        elements = [_element('Paragraph one.'), _element('Paragraph two.')]
        parser = UnstructuredParser(partition_fn=lambda **_: elements)
        documents = parser.parse(b'plain text', _doc(name='a.txt'))
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].page_content, 'Paragraph one.\n\nParagraph two.')

    def test_blank_elements_are_skipped(self):
        elements = [_element('  '), _element('Real content')]
        parser = UnstructuredParser(partition_fn=lambda **_: elements)
        documents = parser.parse(b'text', _doc(name='a.txt'))
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].page_content, 'Real content')

    def test_no_elements_produces_no_documents(self):
        parser = UnstructuredParser(partition_fn=lambda **_: [])
        self.assertEqual(parser.parse(b'', _doc()), [])

    def test_document_metadata_includes_source_document_id_and_filename(self):
        parser = UnstructuredParser(partition_fn=lambda **_: [_element('hello')])
        documents = parser.parse(b'hello', _doc(name='policies/a.txt'))
        self.assertEqual(documents[0].metadata['filename'], 'policies/a.txt')
        self.assertEqual(documents[0].metadata['source_document_id'], 's3://bucket/policies/a.txt')

    def test_generic_partition_failure_becomes_document_parse_error(self):
        def failing_partition(**_):
            raise ValueError('corrupt PDF')

        parser = UnstructuredParser(partition_fn=failing_partition)
        with self.assertRaises(DocumentParseError):
            parser.parse(b'bad', _doc(name='a.pdf'))

    def test_missing_format_extra_becomes_unsupported_document_error(self):
        def failing_partition(**_):
            raise ImportError('python-docx is not installed')

        parser = UnstructuredParser(partition_fn=failing_partition)
        with self.assertRaises(UnsupportedDocumentError):
            parser.parse(b'bad', _doc(name='a.docx'))

    def test_partition_is_called_with_the_filename_hint(self):
        partition_fn = mock.Mock(return_value=[])
        parser = UnstructuredParser(partition_fn=partition_fn)
        parser.parse(b'hello', _doc(name='a.md'))
        _, kwargs = partition_fn.call_args
        self.assertEqual(kwargs['metadata_filename'], 'a.md')

    def test_content_type_hint_is_forwarded_when_present(self):
        partition_fn = mock.Mock(return_value=[])
        parser = UnstructuredParser(partition_fn=partition_fn)
        parser.parse(b'hello', _doc(name='a.html', content_type='text/html'))
        _, kwargs = partition_fn.call_args
        self.assertEqual(kwargs['content_type'], 'text/html')


if __name__ == '__main__':
    unittest.main()
