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

from dapr.ext.rag.embedding.azure_openai import AzureOpenAIEmbedder
from dapr.ext.rag.errors import OptionalDependencyError, TransientEmbeddingError


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


class _FakeAzureOpenAIClient:
    def __init__(self, response=None, exception=None):
        self.embeddings = _FakeEmbeddings(response=response, exception=exception)


def _response(items):
    data = [SimpleNamespace(index=index, embedding=embedding) for index, embedding in items]
    return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=len(items)))


def _fake_error(name, status_code=None, retry_after=None):
    error_cls = type(name, (Exception,), {})
    error = error_cls('boom')
    if status_code is not None:
        error.status_code = status_code
    if retry_after is not None:
        error.response = SimpleNamespace(headers={'retry-after': str(retry_after)})
    return error


class AzureOpenAIEmbedderConstructionTest(unittest.TestCase):
    def test_raises_optional_dependency_error_without_openai_or_client(self):
        with mock.patch('dapr.ext.rag.embedding._openai_common.openai', None):
            with self.assertRaises(OptionalDependencyError) as ctx:
                AzureOpenAIEmbedder(
                    endpoint='https://x.openai.azure.com', deployment='text-embedding-3-small'
                )
        self.assertEqual(ctx.exception.package, 'openai')

    def test_raises_optional_dependency_error_for_missing_azure_identity(self):
        fake_openai_module = mock.Mock()
        with mock.patch('dapr.ext.rag.embedding._openai_common.openai', fake_openai_module):
            with mock.patch('dapr.ext.rag.embedding._openai_common.DefaultAzureCredential', None):
                with self.assertRaises(OptionalDependencyError) as ctx:
                    AzureOpenAIEmbedder(
                        endpoint='https://x.openai.azure.com', deployment='text-embedding-3-small'
                    )
        self.assertEqual(ctx.exception.package, 'azure-identity')

    def test_client_injection_bypasses_dependency_checks(self):
        with mock.patch('dapr.ext.rag.embedding._openai_common.openai', None):
            embedder = AzureOpenAIEmbedder(
                endpoint='https://x.openai.azure.com',
                deployment='embed-deploy',
                client=_FakeAzureOpenAIClient(response=_response([])),
            )
        self.assertEqual(embedder.deployment, 'embed-deploy')

    def test_model_defaults_to_deployment_name(self):
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com',
            deployment='text-embedding-3-small',
            client=_FakeAzureOpenAIClient(),
        )
        self.assertEqual(embedder.embedding_model, 'text-embedding-3-small')

    def test_model_can_be_set_separately_from_deployment(self):
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com',
            deployment='my-custom-deployment',
            model='text-embedding-3-small',
            client=_FakeAzureOpenAIClient(),
        )
        self.assertEqual(embedder.deployment, 'my-custom-deployment')
        self.assertEqual(embedder.embedding_model, 'text-embedding-3-small')

    def test_config_never_includes_the_api_key(self):
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com',
            deployment='d',
            api_key='super-secret-key',
            client=_FakeAzureOpenAIClient(),
        )
        self.assertNotIn('super-secret-key', str(embedder.config()))


class AzureOpenAIEmbedderEmbedBatchTest(unittest.TestCase):
    def test_addresses_the_request_by_deployment_name(self):
        client = _FakeAzureOpenAIClient(response=_response([(0, [0.1])]))
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com', deployment='my-deployment', client=client
        )
        embedder.embed_batch(['hello'])
        self.assertEqual(client.embeddings.calls[0]['model'], 'my-deployment')

    def test_returns_embeddings_in_order(self):
        client = _FakeAzureOpenAIClient(response=_response([(1, [0.2]), (0, [0.1])]))
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com', deployment='d', client=client
        )
        result = embedder.embed_batch(['a', 'b'])
        self.assertEqual(result.embeddings, [[0.1], [0.2]])


class AzureOpenAIEmbedderErrorClassificationTest(unittest.TestCase):
    def test_408_is_treated_as_transient(self):
        client = _FakeAzureOpenAIClient(
            exception=_fake_error('SomeTimeoutStatusError', status_code=408)
        )
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com', deployment='d', client=client
        )
        with self.assertRaises(TransientEmbeddingError):
            embedder.embed_batch(['text'])

    def test_retry_after_header_is_surfaced_on_the_exception(self):
        client = _FakeAzureOpenAIClient(exception=_fake_error('RateLimitError', retry_after=2.5))
        embedder = AzureOpenAIEmbedder(
            endpoint='https://x.openai.azure.com', deployment='d', client=client
        )
        with self.assertRaises(TransientEmbeddingError) as ctx:
            embedder.embed_batch(['text'])
        self.assertEqual(ctx.exception.retry_after_seconds, 2.5)


if __name__ == '__main__':
    unittest.main()
