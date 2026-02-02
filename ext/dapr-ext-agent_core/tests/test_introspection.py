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

from dapr.ext.agent_core.introspection import detect_framework


class DetectFrameworkTest(unittest.TestCase):
    """Tests for detect_framework function."""

    def test_detect_langgraph_by_class_name(self):
        """Test detection of LangGraph by CompiledStateGraph class name."""

        class CompiledStateGraph:
            pass

        agent = CompiledStateGraph()
        result = detect_framework(agent)
        self.assertEqual(result, 'langgraph')

    def test_detect_langgraph_by_module(self):
        """Test detection of LangGraph by module path."""

        class MockGraph:
            pass

        MockGraph.__module__ = 'langgraph.graph.state'
        agent = MockGraph()
        result = detect_framework(agent)
        self.assertEqual(result, 'langgraph')

    def test_detect_dapr_agents_by_module(self):
        """Test detection of dapr-agents by module path."""

        class MockAgent:
            pass

        MockAgent.__module__ = 'dapr_agents.agents.base'
        agent = MockAgent()
        result = detect_framework(agent)
        self.assertEqual(result, 'dapr_agents')

    def test_detect_strands_by_class_name(self):
        """Test detection of Strands by DaprSessionManager class name."""

        class DaprSessionManager:
            pass

        agent = DaprSessionManager()
        result = detect_framework(agent)
        self.assertEqual(result, 'strands')

    def test_detect_strands_by_module(self):
        """Test detection of Strands by module path."""

        class MockSessionManager:
            pass

        MockSessionManager.__module__ = 'strands.session.manager'
        agent = MockSessionManager()
        result = detect_framework(agent)
        self.assertEqual(result, 'strands')

    def test_detect_unknown_framework(self):
        """Test detection returns None for unknown frameworks."""

        class UnknownAgent:
            pass

        UnknownAgent.__module__ = 'some.unknown.module'
        agent = UnknownAgent()
        result = detect_framework(agent)
        self.assertIsNone(result)

    def test_detect_builtin_object(self):
        """Test detection returns None for builtin objects."""
        result = detect_framework('string')
        self.assertIsNone(result)

        result = detect_framework(42)
        self.assertIsNone(result)

        result = detect_framework([1, 2, 3])
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
