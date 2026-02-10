# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

# Tests for data models.

import json

from dapr.ext.crewai.models import (
    AgentConfig,
    AgentWorkflowInput,
    AgentWorkflowOutput,
    CallLlmInput,
    ExecuteToolInput,
    Message,
    MessageRole,
    TaskConfig,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


class TestToolCall:
    def test_to_dict(self):
        tc = ToolCall(id='call_123', name='search', args={'query': 'test'})
        result = tc.to_dict()
        assert result == {
            'id': 'call_123',
            'name': 'search',
            'args': {'query': 'test'},
        }

    def test_from_dict(self):
        data = {'id': 'call_123', 'name': 'search', 'args': {'query': 'test'}}
        tc = ToolCall.from_dict(data)
        assert tc.id == 'call_123'
        assert tc.name == 'search'
        assert tc.args == {'query': 'test'}

    def test_roundtrip(self):
        original = ToolCall(id='call_123', name='search', args={'query': 'test'})
        roundtripped = ToolCall.from_dict(original.to_dict())
        assert original.id == roundtripped.id
        assert original.name == roundtripped.name
        assert original.args == roundtripped.args


class TestToolResult:
    def test_to_dict(self):
        tr = ToolResult(
            tool_call_id='call_123',
            tool_name='search',
            result='Found 10 results',
        )
        result = tr.to_dict()
        assert result['tool_call_id'] == 'call_123'
        assert result['tool_name'] == 'search'
        assert result['result'] == 'Found 10 results'
        assert result['error'] is None

    def test_from_dict_with_error(self):
        data = {
            'tool_call_id': 'call_123',
            'tool_name': 'search',
            'result': None,
            'error': 'Tool not found',
        }
        tr = ToolResult.from_dict(data)
        assert tr.error == 'Tool not found'
        assert tr.result is None


class TestMessage:
    def test_user_message(self):
        msg = Message(role=MessageRole.USER, content='Hello')
        data = msg.to_dict()
        assert data['role'] == 'user'
        assert data['content'] == 'Hello'
        assert data['tool_calls'] == []

    def test_assistant_message_with_tool_calls(self):
        tc = ToolCall(id='call_123', name='search', args={'query': 'test'})
        msg = Message(
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[tc],
        )
        data = msg.to_dict()
        assert data['role'] == 'assistant'
        assert len(data['tool_calls']) == 1
        assert data['tool_calls'][0]['name'] == 'search'

    def test_tool_message(self):
        msg = Message(
            role=MessageRole.TOOL,
            content='Result: success',
            tool_call_id='call_123',
            name='search',
        )
        data = msg.to_dict()
        assert data['role'] == 'tool'
        assert data['tool_call_id'] == 'call_123'
        assert data['name'] == 'search'

    def test_roundtrip(self):
        tc = ToolCall(id='call_123', name='search', args={'query': 'test'})
        original = Message(
            role=MessageRole.ASSISTANT,
            content='Let me search',
            tool_calls=[tc],
        )
        roundtripped = Message.from_dict(original.to_dict())
        assert original.role == roundtripped.role
        assert original.content == roundtripped.content
        assert len(original.tool_calls) == len(roundtripped.tool_calls)


class TestAgentConfig:
    def test_to_dict(self):
        config = AgentConfig(
            role='Research Assistant',
            goal='Help users',
            backstory='An expert',
            model='gpt-4o-mini',
            tool_definitions=[
                ToolDefinition(name='search', description='Search the web'),
            ],
        )
        data = config.to_dict()
        assert data['role'] == 'Research Assistant'
        assert data['model'] == 'gpt-4o-mini'
        assert len(data['tool_definitions']) == 1

    def test_from_dict(self):
        data = {
            'role': 'Assistant',
            'goal': 'Help',
            'backstory': 'Expert',
            'model': 'gpt-4',
            'tool_definitions': [],
            'max_iter': 30,
            'verbose': True,
        }
        config = AgentConfig.from_dict(data)
        assert config.role == 'Assistant'
        assert config.max_iter == 30
        assert config.verbose is True


class TestAgentWorkflowInput:
    def test_json_serializable(self):
        """Test that the entire input can be JSON serialized."""
        agent_config = AgentConfig(
            role='Assistant',
            goal='Help',
            backstory='Expert',
            model='gpt-4',
        )
        task_config = TaskConfig(
            description='Do something',
            expected_output='A result',
        )
        workflow_input = AgentWorkflowInput(
            agent_config=agent_config,
            task_config=task_config,
            messages=[Message(role=MessageRole.USER, content='Hello')],
            session_id='test-session',
        )

        # Should not raise
        json_str = json.dumps(workflow_input.to_dict())
        assert json_str is not None

        # Should roundtrip
        parsed = AgentWorkflowInput.from_dict(json.loads(json_str))
        assert parsed.session_id == 'test-session'
        assert parsed.agent_config.role == 'Assistant'


class TestAgentWorkflowOutput:
    def test_completed_output(self):
        output = AgentWorkflowOutput(
            final_response='The answer is 42',
            messages=[],
            iterations=3,
            status='completed',
        )
        data = output.to_dict()
        assert data['final_response'] == 'The answer is 42'
        assert data['iterations'] == 3
        assert data['status'] == 'completed'

    def test_error_output(self):
        output = AgentWorkflowOutput(
            final_response=None,
            messages=[],
            iterations=1,
            status='error',
            error='Something went wrong',
        )
        data = output.to_dict()
        assert data['error'] == 'Something went wrong'


class TestCallLlmInput:
    def test_to_dict(self):
        agent_config = AgentConfig(
            role='Assistant',
            goal='Help',
            backstory='Expert',
            model='gpt-4',
        )
        task_config = TaskConfig(
            description='Do something',
            expected_output='A result',
        )
        llm_input = CallLlmInput(
            agent_config=agent_config,
            task_config=task_config,
            messages=[],
        )
        data = llm_input.to_dict()
        assert 'agent_config' in data
        assert 'task_config' in data
        assert 'messages' in data


class TestExecuteToolInput:
    def test_to_dict(self):
        tc = ToolCall(id='call_123', name='search', args={'query': 'test'})
        tool_input = ExecuteToolInput(
            tool_call=tc,
            agent_role='Assistant',
            session_id='test-session',
        )
        data = tool_input.to_dict()
        assert data['tool_call']['id'] == 'call_123'
        assert data['agent_role'] == 'Assistant'
        assert data['session_id'] == 'test-session'
