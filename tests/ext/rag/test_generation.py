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

from dapr.ext.rag.errors import InvalidGenerationRequestError, TransientGenerationError
from dapr.ext.rag.generation import AzureOpenAIChatClient
from dapr.ext.rag.models import QueryMatch


class _FakeChatCompletions:
    def __init__(self, answer_text='the answer', exception=None):
        self._answer_text = answer_text
        self._exception = exception
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        message = SimpleNamespace(content=self._answer_text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeChatClient:
    def __init__(self, answer_text='the answer', exception=None):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(answer_text, exception))


def _match(chunk_id='c1', document_id='doc-1', content='relevant text', score=0.9, **metadata):
    return QueryMatch(
        chunk_id=chunk_id, document_id=document_id, content=content, score=score, metadata=metadata
    )


def _fake_error(name, status_code=None):
    error_cls = type(name, (Exception,), {})
    error = error_cls('boom')
    if status_code is not None:
        error.status_code = status_code
    return error


class AzureOpenAIChatClientTest(unittest.TestCase):
    def test_generates_an_answer_with_citations(self):
        client = _FakeChatClient(answer_text='The policy allows remote work. [1]')
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com', deployment='chat-deploy', client=client
        )
        matches = [
            _match(
                chunk_id='c1',
                document_id='doc-1',
                source_name='handbook.pdf',
                source_uri='blob://handbook.pdf',
            )
        ]

        result = chat.generate_answer('Can I work remotely?', matches, index_version='2026-09')

        self.assertEqual(result.answer, 'The policy allows remote work. [1]')
        self.assertTrue(result.sufficient_evidence)
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0].chunk_id, 'c1')
        self.assertEqual(result.citations[0].title, 'handbook.pdf')
        self.assertEqual(result.citations[0].source_uri, 'blob://handbook.pdf')
        self.assertEqual(result.index_version, '2026-09')

    def test_addresses_the_request_by_deployment_name(self):
        client = _FakeChatClient()
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com', deployment='my-chat-deploy', client=client
        )
        chat.generate_answer('question', [_match()], index_version='v1')
        self.assertEqual(client.chat.completions.calls[0]['model'], 'my-chat-deploy')

    def test_insufficient_evidence_skips_the_model_call_entirely(self):
        client = _FakeChatClient()
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com',
            deployment='d',
            client=client,
            min_context_matches=1,
        )
        result = chat.generate_answer('question', [], index_version='v1')
        self.assertFalse(result.sufficient_evidence)
        self.assertEqual(result.citations, ())
        self.assertEqual(client.chat.completions.calls, [])

    def test_low_score_matches_are_excluded_from_context_and_the_sufficiency_check(self):
        client = _FakeChatClient()
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com',
            deployment='d',
            client=client,
            min_context_matches=1,
            min_score=0.5,
        )
        result = chat.generate_answer('question', [_match(score=0.1)], index_version='v1')
        self.assertFalse(result.sufficient_evidence)

    def test_workflow_instance_id_is_echoed_back(self):
        client = _FakeChatClient()
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com', deployment='d', client=client
        )
        result = chat.generate_answer(
            'q', [_match()], index_version='v1', workflow_instance_id='wf-1'
        )
        self.assertEqual(result.workflow_instance_id, 'wf-1')

    def test_transient_failure_raises_transient_generation_error(self):
        client = _FakeChatClient(exception=_fake_error('RateLimitError'))
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com', deployment='d', client=client
        )
        with self.assertRaises(TransientGenerationError):
            chat.generate_answer('q', [_match()], index_version='v1')

    def test_invalid_request_raises_invalid_generation_request_error(self):
        client = _FakeChatClient(exception=_fake_error('BadRequestError'))
        chat = AzureOpenAIChatClient(
            endpoint='https://x.openai.azure.com', deployment='d', client=client
        )
        with self.assertRaises(InvalidGenerationRequestError):
            chat.generate_answer('q', [_match()], index_version='v1')


if __name__ == '__main__':
    unittest.main()
