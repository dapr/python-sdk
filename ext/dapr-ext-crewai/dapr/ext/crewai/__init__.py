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

from .models import (
    AgentConfig,
    AgentWorkflowInput,
    AgentWorkflowOutput,
    CallLlmInput,
    CallLlmOutput,
    ExecuteToolInput,
    ExecuteToolOutput,
    Message,
    MessageRole,
    TaskConfig,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from .runner import DaprWorkflowAgentRunner
from .version import __version__
from .workflow import (
    call_llm_activity,
    clear_tool_registry,
    crewai_agent_workflow,
    execute_tool_activity,
    get_registered_tool,
    register_tool,
)

__all__ = [
    # Main runner class
    'DaprWorkflowAgentRunner',
    # Data models
    'AgentConfig',
    'AgentWorkflowInput',
    'AgentWorkflowOutput',
    'CallLlmInput',
    'CallLlmOutput',
    'ExecuteToolInput',
    'ExecuteToolOutput',
    'Message',
    'MessageRole',
    'TaskConfig',
    'ToolCall',
    'ToolDefinition',
    'ToolResult',
    # Workflow and activities (for advanced usage)
    'crewai_agent_workflow',
    'call_llm_activity',
    'execute_tool_activity',
    # Tool registry (for advanced usage)
    'register_tool',
    'get_registered_tool',
    'clear_tool_registry',
    # Version
    '__version__',
]
