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

import string
import unittest

from dapr.ext.rag.models import Document
from dapr.ext.rag.splitting import TextSplitter


class TextSplitterConstructionTest(unittest.TestCase):
    def test_rejects_non_positive_chunk_size(self):
        with self.assertRaises(ValueError):
            TextSplitter(chunk_size=0)

    def test_rejects_negative_overlap(self):
        with self.assertRaises(ValueError):
            TextSplitter(chunk_size=100, chunk_overlap=-1)

    def test_rejects_overlap_not_smaller_than_chunk_size(self):
        with self.assertRaises(ValueError):
            TextSplitter(chunk_size=100, chunk_overlap=100)


class TextSplitterSplitTest(unittest.TestCase):
    def test_short_document_produces_a_single_chunk(self):
        splitter = TextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = splitter.split(Document(page_content='hello world'))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, 'hello world')
        self.assertEqual(chunks[0].chunk_ordinal, 0)

    def test_long_document_is_split_into_multiple_ordered_chunks(self):
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = '\n\n'.join(f'Paragraph number {i} with some filler text.' for i in range(20))
        chunks = splitter.split(Document(page_content=text))
        self.assertGreater(len(chunks), 1)
        self.assertEqual([c.chunk_ordinal for c in chunks], list(range(len(chunks))))

    def test_no_chunk_exceeds_chunk_size_plus_chunk_overlap(self):
        # chunk_size is a target, not always an exact cap once overlap is involved --
        # see splitting.py's _merge_with_overlap comment for the proven hard bound.
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = 'word ' * 500
        chunks = splitter.split(Document(page_content=text))
        for chunk in chunks:
            self.assertLessEqual(len(chunk.content), 60)

    def test_consecutive_chunks_share_overlapping_content(self):
        # Every character below is unique, so a matching substring can only mean a
        # genuine positional overlap -- not a coincidence from a repeated character.
        unique_text = string.ascii_lowercase + string.ascii_uppercase + string.digits
        splitter = TextSplitter(chunk_size=20, chunk_overlap=5, separators=[''])
        chunks = splitter.split(Document(page_content=unique_text))
        self.assertGreaterEqual(len(chunks), 2)
        for first, second in zip(chunks, chunks[1:]):
            self.assertEqual(first.content[-5:], second.content[:5])

    def test_splitting_is_deterministic(self):
        splitter = TextSplitter(chunk_size=30, chunk_overlap=5)
        document = Document(page_content='One two three.\n\nFour five six.\n\nSeven eight nine.')
        first = splitter.split(document)
        second = splitter.split(document)
        self.assertEqual([c.content for c in first], [c.content for c in second])

    def test_chunk_metadata_carries_forward_document_metadata(self):
        splitter = TextSplitter(chunk_size=1000, chunk_overlap=0)
        document = Document(page_content='hello', metadata={'page_number': 3})
        chunks = splitter.split(document)
        self.assertEqual(chunks[0].metadata, {'page_number': 3})

    def test_empty_document_produces_no_chunks(self):
        splitter = TextSplitter()
        self.assertEqual(splitter.split(Document(page_content='')), [])

    def test_config_fingerprint_changes_with_chunk_size(self):
        base = TextSplitter(chunk_size=1000, chunk_overlap=150).config_fingerprint()
        changed = TextSplitter(chunk_size=500, chunk_overlap=150).config_fingerprint()
        self.assertNotEqual(base, changed)

    def test_splitter_type_is_stable(self):
        self.assertEqual(TextSplitter().splitter_type, 'text_splitter')


if __name__ == '__main__':
    unittest.main()
