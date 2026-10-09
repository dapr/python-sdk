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

from dapr.ext.rag.embedding.openai import OpenAIEmbedder
from dapr.ext.rag.errors import (
    InvalidEmbeddingRequestError,
    OptionalDependencyError,
    TransientEmbeddingError,
)


class _FakeEmbeddings:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._response


class _FakeOpenAIClient:
    def __init__(self, response=None, exception=None):
        self.embeddings = _FakeEmbeddings(response=response, exception=exception)


def _response(items, total_tokens=None):
    data = [SimpleNamespace(index=index, embedding=embedding) for index, embedding in items]
    usage = SimpleNamespace(total_tokens=total_tokens) if total_tokens is not None else None
    return SimpleNamespace(data=data, usage=usage)


def _fake_error(name, status_code=None):
    error_cls = type(name, (Exception,), {})
    error = error_cls('boom')
    if status_code is not None:
        error.status_code = status_code
    return error


class OpenAIEmbedderConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_openai_or_client(self):
        with mock.patch('dapr.ext.rag.embedding.openai.openai', None):
            with self.assertRaises(OptionalDependencyError):
                OpenAIEmbedder()

    def test_client_injection_bypasses_the_dependency_check(self):
        with mock.patch('dapr.ext.rag.embedding.openai.openai', None):
            embedder = OpenAIEmbedder(client=_FakeOpenAIClient(response=_response([])))
        self.assertEqual(embedder.embedding_model, 'text-embedding-3-small')

    def test_config_fingerprint_changes_with_model(self):
        small = OpenAIEmbedder(client=_FakeOpenAIClient()).config_fingerprint()
        large = OpenAIEmbedder(
            model='text-embedding-3-large', client=_FakeOpenAIClient()
        ).config_fingerprint()
        self.assertNotEqual(small, large)


class OpenAIEmbedderEmbedBatchTest(unittest.TestCase):
    def test_returns_embeddings_in_input_order_even_if_the_response_is_out_of_order(self):
        response = _response([(1, [0.2, 0.2]), (0, [0.1, 0.1])], total_tokens=42)
        embedder = OpenAIEmbedder(client=_FakeOpenAIClient(response=response))
        result = embedder.embed_batch(['first', 'second'])
        self.assertEqual(result.embeddings, [[0.1, 0.1], [0.2, 0.2]])
        self.assertEqual(result.total_tokens, 42)

    def test_empty_batch_returns_immediately_without_calling_the_client(self):
        client = _FakeOpenAIClient(response=_response([]))
        embedder = OpenAIEmbedder(client=client)
        result = embedder.embed_batch([])
        self.assertEqual(result.embeddings, [])
        self.assertEqual(client.embeddings.calls, [])

    def test_dimensions_are_forwarded_when_configured(self):
        client = _FakeOpenAIClient(response=_response([(0, [0.1])]))
        embedder = OpenAIEmbedder(dimensions=256, client=client)
        embedder.embed_batch(['text'])
        self.assertEqual(client.embeddings.calls[0]['dimensions'], 256)

    def test_dimensions_are_omitted_by_default(self):
        client = _FakeOpenAIClient(response=_response([(0, [0.1])]))
        embedder = OpenAIEmbedder(client=client)
        embedder.embed_batch(['text'])
        self.assertNotIn('dimensions', client.embeddings.calls[0])


class OpenAIEmbedderErrorClassificationTest(unittest.TestCase):
    def test_rate_limit_error_is_transient(self):
        client = _FakeOpenAIClient(exception=_fake_error('RateLimitError'))
        embedder = OpenAIEmbedder(client=client)
        with self.assertRaises(TransientEmbeddingError):
            embedder.embed_batch(['text'])

    def test_bad_request_error_is_non_retryable(self):
        client = _FakeOpenAIClient(exception=_fake_error('BadRequestError'))
        embedder = OpenAIEmbedder(client=client)
        with self.assertRaises(InvalidEmbeddingRequestError):
            embedder.embed_batch(['text'])

    def test_unrecognized_5xx_status_is_transient(self):
        client = _FakeOpenAIClient(exception=_fake_error('SomeFutureServerError', status_code=503))
        embedder = OpenAIEmbedder(client=client)
        with self.assertRaises(TransientEmbeddingError):
            embedder.embed_batch(['text'])

    def test_unrecognized_4xx_status_is_non_retryable(self):
        client = _FakeOpenAIClient(exception=_fake_error('SomeFutureClientError', status_code=422))
        embedder = OpenAIEmbedder(client=client)
        with self.assertRaises(InvalidEmbeddingRequestError):
            embedder.embed_batch(['text'])

    def test_totally_unrecognized_failure_defaults_to_transient(self):
        client = _FakeOpenAIClient(exception=_fake_error('WeirdNetworkGlitch'))
        embedder = OpenAIEmbedder(client=client)
        with self.assertRaises(TransientEmbeddingError):
            embedder.embed_batch(['text'])


if __name__ == '__main__':
    unittest.main()
