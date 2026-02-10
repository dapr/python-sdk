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

from dapr.ext.agent_core.types import (
    AgentMetadata,
    AgentMetadataSchema,
    LLMMetadata,
    MemoryMetadata,
    PubSubMetadata,
    RegistryMetadata,
    SupportedFrameworks,
    ToolMetadata,
)


class SupportedFrameworksTest(unittest.TestCase):
    """Tests for SupportedFrameworks enum."""

    def test_dapr_agents_value(self):
        """Test DAPR_AGENTS enum value."""
        self.assertEqual(SupportedFrameworks.DAPR_AGENTS.value, 'Dapr Agents')

    def test_langgraph_value(self):
        """Test LANGGRAPH enum value."""
        self.assertEqual(SupportedFrameworks.LANGGRAPH.value, 'LangGraph')
    def test_strands_value(self):
        """Test STRANDS enum value."""
        self.assertEqual(SupportedFrameworks.STRANDS.value, 'Strands')

    def test_all_frameworks_present(self):
        """Test all expected frameworks are present."""
        framework_values = [f.value for f in SupportedFrameworks]
        self.assertIn('Dapr Agents', framework_values)
        self.assertIn('LangGraph', framework_values)
        self.assertIn('Strands', framework_values)


class AgentMetadataTest(unittest.TestCase):
    """Tests for AgentMetadata model."""

    def test_minimal_agent_metadata(self):
        """Test AgentMetadata with minimal required fields."""
        agent = AgentMetadata(appid='test-app', type='standalone')
        self.assertEqual(agent.appid, 'test-app')
        self.assertEqual(agent.type, 'standalone')
        self.assertEqual(agent.orchestrator, False)
        self.assertEqual(agent.role, '')
        self.assertEqual(agent.goal, '')

    def test_full_agent_metadata(self):
        """Test AgentMetadata with all fields populated."""
        agent = AgentMetadata(
            appid='test-app',
            type='durable',
            orchestrator=True,
            role='coordinator',
            goal='Manage tasks',
            instructions=['Step 1', 'Step 2'],
            statestore='agent-store',
            system_prompt='You are a helpful assistant.',
        )
        self.assertEqual(agent.appid, 'test-app')
        self.assertEqual(agent.type, 'durable')
        self.assertTrue(agent.orchestrator)
        self.assertEqual(agent.role, 'coordinator')
        self.assertEqual(agent.goal, 'Manage tasks')
        self.assertEqual(agent.instructions, ['Step 1', 'Step 2'])
        self.assertEqual(agent.statestore, 'agent-store')
        self.assertEqual(agent.system_prompt, 'You are a helpful assistant.')


class LLMMetadataTest(unittest.TestCase):
    """Tests for LLMMetadata model."""

    def test_minimal_llm_metadata(self):
        """Test LLMMetadata with minimal required fields."""
        llm = LLMMetadata(client='OpenAI', provider='openai')
        self.assertEqual(llm.client, 'OpenAI')
        self.assertEqual(llm.provider, 'openai')
        self.assertEqual(llm.api, 'unknown')
        self.assertEqual(llm.model, 'unknown')

    def test_azure_llm_metadata(self):
        """Test LLMMetadata with Azure-specific fields."""
        llm = LLMMetadata(
            client='AzureOpenAI',
            provider='azure_openai',
            api='chat',
            model='gpt-4',
            azure_endpoint='https://myresource.openai.azure.com',
            azure_deployment='gpt-4-deployment',
        )
        self.assertEqual(llm.azure_endpoint, 'https://myresource.openai.azure.com')
        self.assertEqual(llm.azure_deployment, 'gpt-4-deployment')


class PubSubMetadataTest(unittest.TestCase):
    """Tests for PubSubMetadata model."""

    def test_minimal_pubsub_metadata(self):
        """Test PubSubMetadata with minimal required fields."""
        pubsub = PubSubMetadata(name='pubsub-component')
        self.assertEqual(pubsub.name, 'pubsub-component')
        self.assertIsNone(pubsub.broadcast_topic)
        self.assertIsNone(pubsub.agent_topic)

    def test_full_pubsub_metadata(self):
        """Test PubSubMetadata with all fields."""
        pubsub = PubSubMetadata(
            name='pubsub-component',
            broadcast_topic='broadcast',
            agent_topic='agent-topic',
        )
        self.assertEqual(pubsub.broadcast_topic, 'broadcast')
        self.assertEqual(pubsub.agent_topic, 'agent-topic')


class ToolMetadataTest(unittest.TestCase):
    """Tests for ToolMetadata model."""

    def test_tool_metadata(self):
        """Test ToolMetadata creation."""
        tool = ToolMetadata(
            tool_name='search',
            tool_description='Search the web',
            tool_args='{"query": "string"}',
        )
        self.assertEqual(tool.tool_name, 'search')
        self.assertEqual(tool.tool_description, 'Search the web')
        self.assertEqual(tool.tool_args, '{"query": "string"}')


class MemoryMetadataTest(unittest.TestCase):
    """Tests for MemoryMetadata model."""

    def test_minimal_memory_metadata(self):
        """Test MemoryMetadata with minimal required fields."""
        memory = MemoryMetadata(type='DaprCheckpointer')
        self.assertEqual(memory.type, 'DaprCheckpointer')
        self.assertIsNone(memory.statestore)
        self.assertIsNone(memory.session_id)

    def test_full_memory_metadata(self):
        """Test MemoryMetadata with all fields."""
        memory = MemoryMetadata(
            type='DaprSessionManager',
            statestore='session-store',
            session_id='session-123',
        )
        self.assertEqual(memory.type, 'DaprSessionManager')
        self.assertEqual(memory.statestore, 'session-store')
        self.assertEqual(memory.session_id, 'session-123')


class RegistryMetadataTest(unittest.TestCase):
    """Tests for RegistryMetadata model."""

    def test_empty_registry_metadata(self):
        """Test RegistryMetadata with defaults."""
        registry = RegistryMetadata()
        self.assertIsNone(registry.statestore)
        self.assertIsNone(registry.name)

    def test_full_registry_metadata(self):
        """Test RegistryMetadata with all fields."""
        registry = RegistryMetadata(statestore='registry-store', name='team-alpha')
        self.assertEqual(registry.statestore, 'registry-store')
        self.assertEqual(registry.name, 'team-alpha')


class AgentMetadataSchemaTest(unittest.TestCase):
    """Tests for AgentMetadataSchema model."""

    def test_minimal_schema(self):
        """Test AgentMetadataSchema with minimal required fields."""
        schema = AgentMetadataSchema(
            schema_version='1.0.0',
            agent=AgentMetadata(appid='test-app', type='standalone'),
            name='test-agent',
            registered_at='2026-01-01T00:00:00Z',
        )
        self.assertEqual(schema.schema_version, '1.0.0')
        self.assertEqual(schema.agent.appid, 'test-app')
        self.assertEqual(schema.name, 'test-agent')
        self.assertIsNone(schema.pubsub)
        self.assertIsNone(schema.memory)
        self.assertIsNone(schema.llm)

    def test_full_schema(self):
        """Test AgentMetadataSchema with all fields."""
        schema = AgentMetadataSchema(
            schema_version='1.0.0',
            agent=AgentMetadata(appid='test-app', type='durable'),
            name='full-agent',
            registered_at='2026-01-01T00:00:00Z',
            pubsub=PubSubMetadata(name='pubsub'),
            memory=MemoryMetadata(type='DaprCheckpointer'),
            llm=LLMMetadata(client='OpenAI', provider='openai'),
            registry=RegistryMetadata(name='team-1'),
            tools=[
                ToolMetadata(tool_name='search', tool_description='Search tool', tool_args='{}')
            ],
            max_iterations=10,
            tool_choice='auto',
            agent_metadata={'custom': 'data'},
        )
        self.assertEqual(schema.name, 'full-agent')
        self.assertEqual(schema.pubsub.name, 'pubsub')
        self.assertEqual(schema.memory.type, 'DaprCheckpointer')
        self.assertEqual(schema.llm.client, 'OpenAI')
        self.assertEqual(len(schema.tools), 1)
        self.assertEqual(schema.max_iterations, 10)
        self.assertEqual(schema.agent_metadata['custom'], 'data')

    def test_export_json_schema(self):
        """Test export_json_schema method."""
        json_schema = AgentMetadataSchema.export_json_schema(version='1.0.0')

        self.assertIn('$schema', json_schema)
        self.assertEqual(json_schema['$schema'], 'https://json-schema.org/draft/2020-12/schema')
        self.assertEqual(json_schema['version'], '1.0.0')
        self.assertIn('properties', json_schema)

    def test_model_dump(self):
        """Test model_dump produces valid dictionary."""
        schema = AgentMetadataSchema(
            schema_version='1.0.0',
            agent=AgentMetadata(appid='test-app', type='standalone'),
            name='test-agent',
            registered_at='2026-01-01T00:00:00Z',
        )
        data = schema.model_dump()

        self.assertIsInstance(data, dict)
        self.assertEqual(data['schema_version'], '1.0.0')
        self.assertEqual(data['name'], 'test-agent')
        self.assertIn('agent', data)


if __name__ == '__main__':
    unittest.main()
