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

# Serializable data models for CrewAI Dapr Workflow integration.

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MessageRole(str, Enum):
    """Role of a message in the conversation."""

    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL = 'tool'
    SYSTEM = 'system'


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    id: str
    name: str
    args: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'args': self.args,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ToolCall':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            args=data['args'],
        )


@dataclass
class ToolResult:
    """Represents the result of a tool execution."""

    tool_call_id: str
    tool_name: str
    result: Any
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tool_call_id': self.tool_call_id,
            'tool_name': self.tool_name,
            'result': self.result,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ToolResult':
        """Create from dictionary."""
        return cls(
            tool_call_id=data['tool_call_id'],
            tool_name=data['tool_name'],
            result=data['result'],
            error=data.get('error'),
        )


@dataclass
class Message:
    """A serializable message in the conversation.

    This is a simplified representation that can be serialized for Dapr workflow state.
    """

    role: MessageRole
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    tool_call_id: Optional[str] = None  # For tool response messages
    name: Optional[str] = None  # Tool name for tool response messages

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'role': self.role.value,
            'content': self.content,
            'tool_calls': [tc.to_dict() for tc in self.tool_calls],
            'tool_results': [tr.to_dict() for tr in self.tool_results],
            'tool_call_id': self.tool_call_id,
            'name': self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Message':
        """Create from dictionary."""
        return cls(
            role=MessageRole(data['role']),
            content=data.get('content'),
            tool_calls=[ToolCall.from_dict(tc) for tc in data.get('tool_calls', [])],
            tool_results=[ToolResult.from_dict(tr) for tr in data.get('tool_results', [])],
            tool_call_id=data.get('tool_call_id'),
            name=data.get('name'),
        )


@dataclass
class ToolDefinition:
    """Serializable tool definition."""

    name: str
    description: str
    parameters: Optional[dict[str, Any]] = None
    result_as_answer: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'result_as_answer': self.result_as_answer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ToolDefinition':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            description=data['description'],
            parameters=data.get('parameters'),
            result_as_answer=data.get('result_as_answer', False),
        )


@dataclass
class AgentConfig:
    """Serializable agent configuration."""

    role: str
    goal: str
    backstory: str
    model: str
    tool_definitions: list[ToolDefinition] = field(default_factory=list)
    max_iter: int = 25
    verbose: bool = False
    allow_delegation: bool = False
    system_template: Optional[str] = None
    prompt_template: Optional[str] = None
    response_template: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'role': self.role,
            'goal': self.goal,
            'backstory': self.backstory,
            'model': self.model,
            'tool_definitions': [td.to_dict() for td in self.tool_definitions],
            'max_iter': self.max_iter,
            'verbose': self.verbose,
            'allow_delegation': self.allow_delegation,
            'system_template': self.system_template,
            'prompt_template': self.prompt_template,
            'response_template': self.response_template,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AgentConfig':
        """Create from dictionary."""
        return cls(
            role=data['role'],
            goal=data['goal'],
            backstory=data['backstory'],
            model=data['model'],
            tool_definitions=[
                ToolDefinition.from_dict(td) for td in data.get('tool_definitions', [])
            ],
            max_iter=data.get('max_iter', 25),
            verbose=data.get('verbose', False),
            allow_delegation=data.get('allow_delegation', False),
            system_template=data.get('system_template'),
            prompt_template=data.get('prompt_template'),
            response_template=data.get('response_template'),
        )


@dataclass
class TaskConfig:
    """Serializable task configuration."""

    description: str
    expected_output: str
    context: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'description': self.description,
            'expected_output': self.expected_output,
            'context': self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'TaskConfig':
        """Create from dictionary."""
        return cls(
            description=data['description'],
            expected_output=data['expected_output'],
            context=data.get('context'),
        )


@dataclass
class AgentWorkflowInput:
    """Input for the CrewAI agent workflow."""

    agent_config: AgentConfig
    task_config: TaskConfig
    messages: list[Message]
    session_id: str
    iteration: int = 0
    max_iterations: int = 25

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'agent_config': self.agent_config.to_dict(),
            'task_config': self.task_config.to_dict(),
            'messages': [m.to_dict() for m in self.messages],
            'session_id': self.session_id,
            'iteration': self.iteration,
            'max_iterations': self.max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AgentWorkflowInput':
        """Create from dictionary."""
        return cls(
            agent_config=AgentConfig.from_dict(data['agent_config']),
            task_config=TaskConfig.from_dict(data['task_config']),
            messages=[Message.from_dict(m) for m in data['messages']],
            session_id=data['session_id'],
            iteration=data.get('iteration', 0),
            max_iterations=data.get('max_iterations', 25),
        )


@dataclass
class AgentWorkflowOutput:
    """Output from the CrewAI agent workflow."""

    final_response: Optional[str]
    messages: list[Message]
    iterations: int
    status: str = 'completed'
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'final_response': self.final_response,
            'messages': [m.to_dict() for m in self.messages],
            'iterations': self.iterations,
            'status': self.status,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AgentWorkflowOutput':
        """Create from dictionary."""
        return cls(
            final_response=data.get('final_response'),
            messages=[Message.from_dict(m) for m in data['messages']],
            iterations=data['iterations'],
            status=data.get('status', 'completed'),
            error=data.get('error'),
        )


@dataclass
class CallLlmInput:
    """Input for the call_llm activity."""

    agent_config: AgentConfig
    task_config: TaskConfig
    messages: list[Message]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'agent_config': self.agent_config.to_dict(),
            'task_config': self.task_config.to_dict(),
            'messages': [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CallLlmInput':
        """Create from dictionary."""
        return cls(
            agent_config=AgentConfig.from_dict(data['agent_config']),
            task_config=TaskConfig.from_dict(data['task_config']),
            messages=[Message.from_dict(m) for m in data['messages']],
        )


@dataclass
class CallLlmOutput:
    """Output from the call_llm activity."""

    message: Message
    is_final: bool
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'message': self.message.to_dict(),
            'is_final': self.is_final,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CallLlmOutput':
        """Create from dictionary."""
        return cls(
            message=Message.from_dict(data['message']),
            is_final=data['is_final'],
            error=data.get('error'),
        )


@dataclass
class ExecuteToolInput:
    """Input for the execute_tool activity."""

    tool_call: ToolCall
    agent_role: str
    session_id: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tool_call': self.tool_call.to_dict(),
            'agent_role': self.agent_role,
            'session_id': self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ExecuteToolInput':
        """Create from dictionary."""
        return cls(
            tool_call=ToolCall.from_dict(data['tool_call']),
            agent_role=data['agent_role'],
            session_id=data['session_id'],
        )


@dataclass
class ExecuteToolOutput:
    """Output from the execute_tool activity."""

    tool_result: ToolResult
    result_as_answer: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tool_result': self.tool_result.to_dict(),
            'result_as_answer': self.result_as_answer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ExecuteToolOutput':
        """Create from dictionary."""
        return cls(
            tool_result=ToolResult.from_dict(data['tool_result']),
            result_as_answer=data.get('result_as_answer', False),
        )
