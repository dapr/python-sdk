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

from dapr.ext.rag.testing import FailureInjector


class FailureInjectorDefaultsTest(unittest.TestCase):
    @mock.patch('dapr.ext.rag.testing.os._exit')
    def test_a_default_injector_never_crashes(self, mock_exit):
        injector = FailureInjector()
        for _ in range(50):
            injector.maybe_fail_before_start('doc-1', attempt=1)
        injector.maybe_fail_during_embedding('doc-1', batch_index=0)
        injector.maybe_fail_after_embedding_before_completion('doc-1', batch_index=0)
        mock_exit.assert_not_called()


class FailureInjectorFailAfterDocumentsTest(unittest.TestCase):
    @mock.patch('dapr.ext.rag.testing.os._exit')
    def test_crashes_only_after_the_configured_count_is_exceeded(self, mock_exit):
        injector = FailureInjector(fail_after_documents=2)
        injector.maybe_fail_before_start('doc-1', attempt=1)
        injector.maybe_fail_before_start('doc-2', attempt=1)
        mock_exit.assert_not_called()
        injector.maybe_fail_before_start('doc-3', attempt=1)
        mock_exit.assert_called_once_with(70)


class FailureInjectorFailDuringBatchTest(unittest.TestCase):
    @mock.patch('dapr.ext.rag.testing.os._exit')
    def test_crashes_only_on_the_configured_batch_index(self, mock_exit):
        injector = FailureInjector(fail_during_batch_index=1)
        injector.maybe_fail_during_embedding('doc-1', batch_index=0)
        mock_exit.assert_not_called()
        injector.maybe_fail_during_embedding('doc-1', batch_index=1)
        mock_exit.assert_called_once()


class FailureInjectorFailAfterEmbeddingTest(unittest.TestCase):
    @mock.patch('dapr.ext.rag.testing.os._exit')
    def test_crashes_only_for_the_configured_document(self, mock_exit):
        injector = FailureInjector(fail_after_embedding_before_completion_for_document='doc-2')
        injector.maybe_fail_after_embedding_before_completion('doc-1', batch_index=0)
        mock_exit.assert_not_called()
        injector.maybe_fail_after_embedding_before_completion('doc-2', batch_index=0)
        mock_exit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
