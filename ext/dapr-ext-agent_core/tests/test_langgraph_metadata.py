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

from dapr.ext.agent_core.mapping.langgraph import LangGraphMapper


class MockCheckpointer:
    """Mock DaprCheckpointer for testing."""

    def __init__(self, state_store_name='test-store'):
        self.state_store_name = state_store_name


class MockCompiledStateGraph:
    """Mock CompiledStateGraph for testing."""

    def __init__(
        self,
        name='test-graph',
        checkpointer=None,
        nodes=None,
    ):
        self._name = name
        self.checkpointer = checkpointer
        self.nodes = nodes or {}

    def get_name(self):
        return self._name


class LangGraphMapperTest(unittest.TestCase):
    """Tests for LangGraphMapper metadata extraction."""

    def test_mapper_instantiation(self):
        """Test that LangGraphMapper can be instantiated."""
        mapper = LangGraphMapper()
        self.assertIsNotNone(mapper)

    @mock.patch('dapr.ext.agent_core.mapping.langgraph.PregelNode')
    def test_basic_metadata_extraction(self, mock_pregel_node):
        """Test basic metadata extraction from a mock graph."""
        checkpointer = MockCheckpointer(state_store_name='my-store')
        graph = MockCompiledStateGraph(
            name='my-graph',
            checkpointer=checkpointer,
            nodes={'__start__': None},
        )

        mapper = LangGraphMapper()
        metadata = mapper.map_agent_metadata(graph, schema_version='1.0.0')

        self.assertEqual(metadata.schema_version, '1.0.0')
        self.assertEqual(metadata.agent.type, 'MockCompiledStateGraph')
        self.assertEqual(metadata.name, 'my-graph')
        self.assertEqual(metadata.memory.type, 'DaprCheckpointer')
        self.assertEqual(metadata.memory.statestore, 'my-store')

    @mock.patch('dapr.ext.agent_core.mapping.langgraph.PregelNode')
    def test_metadata_without_checkpointer(self, mock_pregel_node):
        """Test metadata extraction without a checkpointer."""
        graph = MockCompiledStateGraph(
            name='no-checkpointer-graph',
            checkpointer=None,
            nodes={},
        )

        mapper = LangGraphMapper()
        metadata = mapper.map_agent_metadata(graph, schema_version='1.0.0')

        self.assertIsNone(metadata.memory.statestore)
        self.assertIsNone(metadata.agent.statestore)

    @mock.patch('dapr.ext.agent_core.mapping.langgraph.PregelNode')
    def test_metadata_agent_role_defaults(self, mock_pregel_node):
        """Test agent metadata default values."""
        graph = MockCompiledStateGraph(name='test')

        mapper = LangGraphMapper()
        metadata = mapper.map_agent_metadata(graph, schema_version='1.0.0')

        self.assertEqual(metadata.agent.role, 'Assistant')
        self.assertFalse(metadata.agent.orchestrator)
        self.assertEqual(metadata.agent.appid, '')

    @mock.patch('dapr.ext.agent_core.mapping.langgraph.PregelNode')
    def test_metadata_llm_defaults(self, mock_pregel_node):
        """Test LLM metadata defaults when no LLM is detected."""
        graph = MockCompiledStateGraph(name='test')

        mapper = LangGraphMapper()
        metadata = mapper.map_agent_metadata(graph, schema_version='1.0.0')

        self.assertEqual(metadata.llm.client, '')
        self.assertEqual(metadata.llm.provider, 'unknown')
        self.assertEqual(metadata.llm.model, 'unknown')

    @mock.patch('dapr.ext.agent_core.mapping.langgraph.PregelNode')
    def test_metadata_pubsub_defaults(self, mock_pregel_node):
        """Test PubSub metadata defaults."""
        graph = MockCompiledStateGraph(name='test')

        mapper = LangGraphMapper()
        metadata = mapper.map_agent_metadata(graph, schema_version='1.0.0')

        self.assertEqual(metadata.pubsub.name, '')
        self.assertIsNone(metadata.pubsub.broadcast_topic)
        self.assertIsNone(metadata.pubsub.agent_topic)

    @mock.patch('dapr.ext.agent_core.mapping.langgraph.PregelNode')
    def test_metadata_registered_at_is_set(self, mock_pregel_node):
        """Test registered_at timestamp is set."""
        graph = MockCompiledStateGraph(name='test')

        mapper = LangGraphMapper()
        metadata = mapper.map_agent_metadata(graph, schema_version='1.0.0')

        self.assertIsNotNone(metadata.registered_at)
        self.assertIn('T', metadata.registered_at)


class LangGraphProviderExtractionTest(unittest.TestCase):
    """Tests for LLM provider extraction."""

    def test_extract_openai_provider(self):
        """Test OpenAI provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain_openai.chat'), 'openai')

    def test_extract_azure_provider(self):
        """Test Azure OpenAI provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain.azure_openai'), 'azure_openai')

    def test_extract_anthropic_provider(self):
        """Test Anthropic provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain_anthropic.chat'), 'anthropic')

    def test_extract_ollama_provider(self):
        """Test Ollama provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain_ollama.llms'), 'ollama')

    def test_extract_google_provider(self):
        """Test Google provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain_google.genai'), 'google')

    def test_extract_gemini_provider(self):
        """Test Gemini provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain_gemini.chat'), 'google')

    def test_extract_cohere_provider(self):
        """Test Cohere provider extraction."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('langchain_cohere.chat'), 'cohere')

    def test_extract_unknown_provider(self):
        """Test unknown provider returns 'unknown'."""
        mapper = LangGraphMapper()
        self.assertEqual(mapper._extract_provider('some.unknown.module'), 'unknown')


if __name__ == '__main__':
    unittest.main()
