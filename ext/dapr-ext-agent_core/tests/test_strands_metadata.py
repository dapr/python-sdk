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

from dapr.ext.agent_core.types import SupportedFrameworks
from dapr.ext.agent_core.introspection import detect_framework
from dapr.ext.agent_core.mapping.strands import StrandsMapper


class MockSessionManager:
    """Mock DaprSessionManager for testing."""

    def __init__(self, state_store_name='test-statestore', session_id='test-session-123'):
        self._state_store_name = state_store_name
        self._session_id = session_id

    @property
    def state_store_name(self) -> str:
        return self._state_store_name


class StrandsMapperTest(unittest.TestCase):
    """Tests for StrandsMapper metadata extraction."""

    def test_mapper_instantiation(self):
        """Test that StrandsMapper can be instantiated."""
        mapper = StrandsMapper()
        self.assertIsNotNone(mapper)

    def test_metadata_extraction_basic(self):
        """Test basic metadata extraction from a mock session manager."""
        mock_manager = MockSessionManager()
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertEqual(metadata.schema_version, '1.0.0')
        self.assertEqual(metadata.agent.type, 'Strands')
        self.assertEqual(metadata.agent.role, 'Session Manager')
        self.assertEqual(metadata.agent.orchestrator, False)
        self.assertEqual(
            metadata.agent.goal, 'Manages multi-agent sessions with distributed state storage'
        )

    def test_metadata_memory_extraction(self):
        """Test memory metadata extraction."""
        mock_manager = MockSessionManager(state_store_name='custom-store', session_id='session-456')
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertEqual(metadata.memory.type, 'DaprSessionManager')
        self.assertEqual(metadata.memory.session_id, 'session-456')
        self.assertEqual(metadata.memory.statestore, 'custom-store')

    def test_metadata_name_generation(self):
        """Test agent name generation with session ID."""
        mock_manager = MockSessionManager(session_id='my-session')
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        # Fallback path generates different name
        self.assertEqual(metadata.name, 'strands-session-my-session')

    def test_metadata_name_without_session_id(self):
        """Test agent name generation without session ID."""
        mock_manager = MockSessionManager(session_id=None)
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertEqual(metadata.name, 'strands-session')

    def test_metadata_agent_metadata_field(self):
        """Test agent_metadata field contains framework info."""
        mock_manager = MockSessionManager(state_store_name='store1', session_id='sess1')
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertEqual(metadata.agent_metadata['framework'], 'strands')
        self.assertEqual(metadata.agent_metadata['session_id'], 'sess1')
        self.assertEqual(metadata.agent_metadata['state_store'], 'store1')
        # agent_id is None in fallback path when no SessionAgent exists
        self.assertIsNone(metadata.agent_metadata['agent_id'])

    def test_metadata_registry_defaults(self):
        """Test registry metadata has correct defaults."""
        mock_manager = MockSessionManager()
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertIsNotNone(metadata.registry)
        self.assertIsNone(metadata.registry.statestore)
        self.assertIsNone(metadata.registry.name)

    def test_metadata_optional_fields_are_none(self):
        """Test optional fields are None when not applicable."""
        mock_manager = MockSessionManager()
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertIsNone(metadata.pubsub)
        self.assertIsNone(metadata.llm)
        self.assertEqual(metadata.tools, [])  # Empty list, not None
        self.assertIsNone(metadata.max_iterations)
        self.assertIsNone(metadata.tool_choice)

    def test_metadata_registered_at_is_set(self):
        """Test registered_at timestamp is set."""
        mock_manager = MockSessionManager()
        mapper = StrandsMapper()

        metadata = mapper.map_agent_metadata(mock_manager, schema_version='1.0.0')

        self.assertIsNotNone(metadata.registered_at)
        self.assertIn('T', metadata.registered_at)


class StrandsFrameworkDetectionTest(unittest.TestCase):
    """Tests for framework detection with Strands objects."""

    def test_detect_framework_by_class_name(self):
        """Test detection by DaprSessionManager class name."""

        class DaprSessionManager:
            pass

        mock = DaprSessionManager()
        framework = detect_framework(mock)
        self.assertEqual(framework, 'strands')

    def test_detect_framework_by_module(self):
        """Test detection by strands module path."""

        class MockAgent:
            pass

        # Use actual type name and module that detection looks for
        MockAgent.__module__ = 'strands.agent'
        MockAgent.__name__ = 'Agent'
        mock = MockAgent()
        framework = detect_framework(mock)
        self.assertEqual(framework, 'strands')


if __name__ == '__main__':
    unittest.main()
