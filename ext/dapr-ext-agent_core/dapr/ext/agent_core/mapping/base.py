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

from abc import ABC, abstractmethod
from typing import Any

from dapr.ext.agent_core.types import AgentMetadataSchema


class BaseAgentMapper(ABC):
    """Abstract base class for agent metadata mappers.

    Provides common functionality for extracting metadata from different
    agent frameworks (Strands, LangGraph, Dapr Agents).
    """

    @staticmethod
    def _extract_provider(module_name: str) -> str:
        """Extract provider name from module path.

        Args:
            module_name: Python module name (e.g., 'langchain_openai.chat_models')

        Returns:
            Provider identifier (e.g., 'openai', 'anthropic', 'azure_openai')
        """
        module_lower = module_name.lower()

        # Check more specific providers first
        if 'vertexai' in module_lower:
            return 'vertexai'
        elif 'bedrock' in module_lower:
            return 'bedrock'
        elif 'azure' in module_lower:
            return 'azure_openai'
        elif 'openai' in module_lower:
            return 'openai'
        elif 'anthropic' in module_lower:
            return 'anthropic'
        elif 'ollama' in module_lower:
            return 'ollama'
        elif 'google' in module_lower or 'gemini' in module_lower:
            return 'google'
        elif 'cohere' in module_lower:
            return 'cohere'

        return 'unknown'

    @abstractmethod
    def map_agent_metadata(self, agent: Any, schema_version: str) -> AgentMetadataSchema:
        """Map agent to standardized metadata schema.

        Args:
            agent: Framework-specific agent instance
            schema_version: Schema version to use

        Returns:
            AgentMetadataSchema with extracted metadata
        """
        pass
