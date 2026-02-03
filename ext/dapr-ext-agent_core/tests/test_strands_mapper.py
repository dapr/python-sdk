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

import json
import time
import unittest
from unittest import mock

from dapr.ext.agent_core.mapping.strands import StrandsMapper


def make_mock_session_manager(session_id='test-session', state_store='statestore'):
    """Create a mock DaprSessionManager for testing."""
    mock_manager = mock.Mock()
    mock_manager._session_id = session_id
    mock_manager._state_store_name = state_store
    mock_manager.state_store_name = state_store  # Public property
    return mock_manager


def make_mock_session_agent(agent_id='test-agent', state=None):
    """Create a mock SessionAgent for testing."""
    mock_agent = mock.Mock()
    mock_agent.agent_id = agent_id
    mock_agent.state = state or {}
    mock_agent.conversation_manager_state = {}
    mock_agent.created_at = time.time()
    return mock_agent


class TestStrandsMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = StrandsMapper()

    def test_map_agent_metadata_no_session_agent(self):
        """Test mapping when no SessionAgent exists in the session."""
        session_manager = make_mock_session_manager()
        session_manager._read_state.return_value = None
        
        result = self.mapper.map_agent_metadata(session_manager, "edge")
        
        # Should use fallback values
        self.assertEqual(result.schema_version, "edge")
        self.assertEqual(result.agent.role, "Session Manager")
        self.assertEqual(result.agent.type, "Strands")
        self.assertIsNone(result.llm)
        self.assertEqual(result.tools, [])  # Empty list, not None
        self.assertIsNone(result.tool_choice)
        self.assertIsNone(result.max_iterations)
        self.assertEqual(result.name, "strands-session-test-session")

    def test_map_agent_metadata_with_basic_agent(self):
        """Test mapping with a basic SessionAgent."""
        session_manager = make_mock_session_manager()
        
        # Mock manifest
        session_manager._read_state.return_value = {'agents': ['assistant']}
        
        # Mock agent
        agent_state = {
            'system_prompt': 'You are a helpful assistant',
            'role': 'AI Assistant',
            'goal': 'Help users',
        }
        mock_agent = make_mock_session_agent('assistant', agent_state)
        session_manager.read_agent.return_value = mock_agent
        
        result = self.mapper.map_agent_metadata(session_manager, "edge")
        
        # Should extract from SessionAgent
        self.assertEqual(result.agent.role, "AI Assistant")
        self.assertEqual(result.agent.goal, "Help users")
        self.assertEqual(result.agent.system_prompt, "You are a helpful assistant")
        self.assertEqual(result.name, "strands-test-session-assistant")
        self.assertEqual(result.agent_metadata['agent_id'], 'assistant')

    def test_map_agent_metadata_with_llm_config(self):
        """Test mapping with LLM configuration."""
        session_manager = make_mock_session_manager()
        session_manager._read_state.return_value = {'agents': ['assistant']}
        
        agent_state = {
            'system_prompt': 'You are helpful',
            'conversation_provider': 'openai',
            'llm_config': {
                'provider': 'openai',
                'model': 'gpt-4',
            }
        }
        mock_agent = make_mock_session_agent('assistant', agent_state)
        session_manager.read_agent.return_value = mock_agent
        
        result = self.mapper.map_agent_metadata(session_manager, "edge")
        
        # Should extract LLM metadata
        self.assertIsNotNone(result.llm)
        self.assertEqual(result.llm.client, "dapr_conversation")
        self.assertEqual(result.llm.provider, "openai")
        self.assertEqual(result.llm.model, "gpt-4")
        self.assertEqual(result.llm.component_name, "openai")

    def test_map_agent_metadata_with_tools(self):
        """Test mapping with tools configuration."""
        session_manager = make_mock_session_manager()
        session_manager._read_state.return_value = {'agents': ['assistant']}
        
        agent_state = {
            'tools': [
                {'name': 'calculator', 'description': 'Calculate math', 'args': {'x': 'int', 'y': 'int'}},
                {'name': 'search', 'description': 'Search web', 'args': {'query': 'str'}},
            ],
            'tool_choice': 'auto',
        }
        mock_agent = make_mock_session_agent('assistant', agent_state)
        session_manager.read_agent.return_value = mock_agent
        
        result = self.mapper.map_agent_metadata(session_manager, "edge")
        
        # Should extract tools metadata
        self.assertIsNotNone(result.tools)
        self.assertEqual(len(result.tools), 2)
        self.assertEqual(result.tools[0].tool_name, 'calculator')
        self.assertEqual(result.tools[0].tool_description, 'Calculate math')
        self.assertEqual(result.tools[1].tool_name, 'search')
        self.assertEqual(result.tool_choice, 'auto')

    def test_map_agent_metadata_with_instructions(self):
        """Test mapping with instructions."""
        session_manager = make_mock_session_manager()
        session_manager._read_state.return_value = {'agents': ['assistant']}
        
        agent_state = {
            'instructions': ['Be concise', 'Be helpful', 'Be friendly'],
            'max_iterations': 10,
        }
        mock_agent = make_mock_session_agent('assistant', agent_state)
        session_manager.read_agent.return_value = mock_agent
        
        result = self.mapper.map_agent_metadata(session_manager, "edge")
        
        # Should extract instructions and max_iterations
        self.assertIsNotNone(result.agent.instructions)
        self.assertEqual(len(result.agent.instructions), 3)
        self.assertEqual(result.agent.instructions[0], 'Be concise')
        self.assertEqual(result.max_iterations, 10)

    def test_extract_llm_metadata_no_config(self):
        """Test LLM metadata extraction with no configuration."""
        result = self.mapper._extract_llm_metadata({})
        self.assertIsNone(result)

    def test_extract_tools_metadata_no_tools(self):
        """Test tools metadata extraction with no tools."""
        result = self.mapper._extract_tools_metadata({})
        self.assertEqual(result, [])  # Empty list, not None

    def test_extract_tools_metadata_with_tool_objects(self):
        """Test tools metadata extraction with tool objects."""
        mock_tool = mock.Mock()
        mock_tool.name = 'my_tool'
        mock_tool.description = 'My tool description'
        mock_tool.args = {'param': 'value'}
        
        agent_state = {'tools': [mock_tool]}
        result = self.mapper._extract_tools_metadata(agent_state)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tool_name, 'my_tool')
        self.assertEqual(result[0].tool_description, 'My tool description')


if __name__ == '__main__':
    unittest.main()
