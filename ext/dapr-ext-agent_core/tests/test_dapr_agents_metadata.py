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

from dapr.ext.agent_core.mapping.dapr_agents import DaprAgentsMapper


class MockProfile:
    """Mock agent profile for testing."""

    def __init__(self, role='assistant', goal='Help users', system_prompt='You are helpful.'):
        self.role = role
        self.goal = goal
        self.instructions = ['Instruction 1', 'Instruction 2']
        self.system_prompt = system_prompt


class MockMemory:
    """Mock memory for testing."""

    def __init__(self, store_name='memory-store', session_id='session-1'):
        self.store_name = store_name
        self.session_id = session_id


class MockPubSub:
    """Mock pubsub for testing."""

    def __init__(self, pubsub_name='pubsub-component'):
        self.pubsub_name = pubsub_name
        self.broadcast_topic = 'broadcast'
        self.agent_topic = 'agent-topic'


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self):
        self.provider = 'openai'
        self.api = 'chat'
        self.model = 'gpt-4'
        self.component_name = None
        self.base_url = None
        self.azure_endpoint = None
        self.azure_deployment = None
        self.prompt_template = None


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name='search', description='Search tool'):
        self.name = name
        self.description = description
        self.args_schema = {'query': 'string'}


class MockRegistry:
    """Mock registry for testing."""

    def __init__(self):
        self.store = MockRegistryStore()
        self.team_name = 'team-alpha'


class MockRegistryStore:
    """Mock registry store for testing."""

    def __init__(self):
        self.store_name = 'registry-store'


class MockExecution:
    """Mock execution config for testing."""

    def __init__(self):
        self.max_iterations = 10
        self.tool_choice = 'auto'


class MockDaprAgent:
    """Mock Dapr agent for testing."""

    def __init__(
        self,
        name='test-agent',
        appid='test-app',
        profile=None,
        memory=None,
        pubsub=None,
        llm=None,
        tools=None,
        registry=None,
        execution=None,
    ):
        self.name = name
        self.appid = appid
        self.profile = profile
        self.memory = memory
        self.pubsub = pubsub
        self.llm = llm
        self.tools = tools or []
        self._registry = registry
        self.execution = execution
        self.agent_metadata = {'custom_key': 'custom_value'}


class DaprAgentsMapperTest(unittest.TestCase):
    """Tests for DaprAgentsMapper metadata extraction."""

    def test_mapper_instantiation(self):
        """Test that DaprAgentsMapper can be instantiated."""
        mapper = DaprAgentsMapper()
        self.assertIsNotNone(mapper)

    def test_minimal_agent_metadata_extraction(self):
        """Test metadata extraction with minimal agent configuration."""
        agent = MockDaprAgent(name='minimal-agent', appid='app-1')
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.schema_version, '1.0.0')
        self.assertEqual(metadata.name, 'minimal-agent')
        self.assertEqual(metadata.agent.appid, 'app-1')
        self.assertEqual(metadata.agent.type, 'MockDaprAgent')

    def test_full_agent_metadata_extraction(self):
        """Test metadata extraction with full agent configuration."""
        agent = MockDaprAgent(
            name='full-agent',
            appid='app-2',
            profile=MockProfile(role='coordinator', goal='Coordinate tasks'),
            memory=MockMemory(store_name='mem-store', session_id='sess-1'),
            pubsub=MockPubSub(pubsub_name='ps-component'),
            llm=MockLLM(),
            tools=[MockTool(name='tool1', description='Tool 1')],
            registry=MockRegistry(),
            execution=MockExecution(),
        )
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        # Agent metadata
        self.assertEqual(metadata.agent.role, 'coordinator')
        self.assertEqual(metadata.agent.goal, 'Coordinate tasks')
        self.assertEqual(metadata.agent.statestore, 'mem-store')
        self.assertEqual(metadata.agent.system_prompt, 'You are helpful.')

        # Memory metadata
        self.assertEqual(metadata.memory.type, 'MockMemory')
        self.assertEqual(metadata.memory.statestore, 'mem-store')
        self.assertEqual(metadata.memory.session_id, 'sess-1')

        # PubSub metadata
        self.assertEqual(metadata.pubsub.name, 'ps-component')
        self.assertEqual(metadata.pubsub.broadcast_topic, 'broadcast')
        self.assertEqual(metadata.pubsub.agent_topic, 'agent-topic')

        # LLM metadata
        self.assertEqual(metadata.llm.provider, 'openai')
        self.assertEqual(metadata.llm.model, 'gpt-4')

        # Tools
        self.assertEqual(len(metadata.tools), 1)
        self.assertEqual(metadata.tools[0].tool_name, 'tool1')

        # Registry
        self.assertEqual(metadata.registry.name, 'team-alpha')
        self.assertEqual(metadata.registry.statestore, 'registry-store')

        # Execution
        self.assertEqual(metadata.max_iterations, 10)
        self.assertEqual(metadata.tool_choice, 'auto')

    def test_agent_metadata_field(self):
        """Test agent_metadata field is preserved."""
        agent = MockDaprAgent()
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.agent_metadata, {'custom_key': 'custom_value'})

    def test_profile_instructions_extraction(self):
        """Test profile instructions are extracted."""
        agent = MockDaprAgent(profile=MockProfile())
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.agent.instructions, ['Instruction 1', 'Instruction 2'])

    def test_registered_at_is_set(self):
        """Test registered_at timestamp is set."""
        agent = MockDaprAgent()
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertIsNotNone(metadata.registered_at)
        self.assertIn('T', metadata.registered_at)

    def test_empty_tools_list(self):
        """Test empty tools list is handled."""
        agent = MockDaprAgent(tools=[])
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.tools, [])

    def test_multiple_tools(self):
        """Test multiple tools are extracted."""
        tools = [
            MockTool(name='tool1', description='First tool'),
            MockTool(name='tool2', description='Second tool'),
        ]
        agent = MockDaprAgent(tools=tools)
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(len(metadata.tools), 2)
        tool_names = [t.tool_name for t in metadata.tools]
        self.assertIn('tool1', tool_names)
        self.assertIn('tool2', tool_names)

    def test_none_profile(self):
        """Test handling of None profile."""
        agent = MockDaprAgent(profile=None)
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.agent.role, '')
        self.assertEqual(metadata.agent.goal, '')
        self.assertEqual(metadata.agent.system_prompt, '')

    def test_none_memory(self):
        """Test handling of None memory."""
        agent = MockDaprAgent(memory=None)
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.memory.type, '')
        self.assertIsNone(metadata.memory.statestore)

    def test_none_llm(self):
        """Test handling of None LLM."""
        agent = MockDaprAgent(llm=None)
        mapper = DaprAgentsMapper()

        metadata = mapper.map_agent_metadata(agent, schema_version='1.0.0')

        self.assertEqual(metadata.llm.client, '')
        self.assertEqual(metadata.llm.provider, 'unknown')


if __name__ == '__main__':
    unittest.main()
