from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SupportedFrameworks(StrEnum):
    DAPR_AGENTS = 'dapr_agents'
    LANGGRAPH = 'langgraph'
    STRANDS = 'strands'


class AgentMetadata(BaseModel):
    """Metadata about an agent's configuration and capabilities."""

    appid: str = Field(..., description='Dapr application ID of the agent')
    type: str = Field(..., description='Type of the agent (e.g., standalone, durable)')
    orchestrator: bool = Field(False, description='Indicates if the agent is an orchestrator')
    role: str = Field(default='', description='Role of the agent')
    goal: str = Field(default='', description='High-level objective of the agent')
    instructions: Optional[List[str]] = Field(
        default=None, description='Instructions for the agent'
    )
    statestore: Optional[str] = Field(
        default=None, description='Dapr state store component name used by the agent'
    )
    system_prompt: Optional[str] = Field(
        default=None, description="System prompt guiding the agent's behavior"
    )


class PubSubMetadata(BaseModel):
    """Pub/Sub configuration information."""

    name: str = Field(..., description='Pub/Sub component name')
    broadcast_topic: Optional[str] = Field(
        default=None, description='Pub/Sub topic for broadcasting messages'
    )
    agent_topic: Optional[str] = Field(
        default=None, description='Pub/Sub topic for direct agent messages'
    )


class MemoryMetadata(BaseModel):
    """Memory configuration information."""

    type: str = Field(..., description='Type of memory used by the agent')
    statestore: Optional[str] = Field(
        default=None, description='Dapr state store component name for memory'
    )
    session_id: Optional[str] = Field(
        default=None, description="Default session ID for the agent's memory"
    )


class LLMMetadata(BaseModel):
    """LLM configuration information."""

    client: str = Field(..., description='LLM client used by the agent')
    provider: str = Field(..., description='LLM provider used by the agent')
    api: str = Field(default='unknown', description='API type used by the LLM client')
    model: str = Field(default='unknown', description='Model name or identifier')
    component_name: Optional[str] = Field(
        default=None, description='Dapr component name for the LLM client'
    )
    base_url: Optional[str] = Field(
        default=None, description='Base URL for the LLM API if applicable'
    )
    azure_endpoint: Optional[str] = Field(
        default=None, description='Azure endpoint if using Azure OpenAI'
    )
    azure_deployment: Optional[str] = Field(
        default=None, description='Azure deployment name if using Azure OpenAI'
    )
    prompt_template: Optional[str] = Field(
        default=None, description='Prompt template used by the agent'
    )


class ToolMetadata(BaseModel):
    """Metadata about a tool available to the agent."""

    tool_name: str = Field(..., description='Name of the tool')
    tool_description: str = Field(..., description="Description of the tool's functionality")
    tool_args: str = Field(..., description='Arguments for the tool')


class RegistryMetadata(BaseModel):
    """Registry configuration information."""

    statestore: Optional[str] = Field(
        None, description='Name of the statestore component for the registry'
    )
    name: Optional[str] = Field(default=None, description='Name of the team registry')


class AgentMetadataSchema(BaseModel):
    """Schema for agent metadata including schema version."""

    schema_version: str = Field(
        ...,
        description='Version of the schema used for the agent metadata.',
    )
    agent: AgentMetadata = Field(..., description='Agent configuration and capabilities')
    name: str = Field(..., description='Name of the agent')
    registered_at: str = Field(..., description='ISO 8601 timestamp of registration')
    pubsub: Optional[PubSubMetadata] = Field(None, description='Pub/sub configuration if enabled')
    memory: Optional[MemoryMetadata] = Field(None, description='Memory configuration if enabled')
    llm: Optional[LLMMetadata] = Field(None, description='LLM configuration')
    registry: Optional[RegistryMetadata] = Field(None, description='Registry configuration')
    tools: Optional[List[ToolMetadata]] = Field(None, description='Available tools')
    max_iterations: Optional[int] = Field(
        None, description='Maximum iterations for agent execution'
    )
    tool_choice: Optional[str] = Field(None, description='Tool choice strategy')
    agent_metadata: Optional[Dict[str, Any]] = Field(
        None, description='Additional metadata about the agent'
    )

    @classmethod
    def export_json_schema(cls, version: str) -> Dict[str, Any]:
        """
        Export the JSON schema with version information.

        Args:
            version: The dapr-agents version for this schema

        Returns:
            JSON schema dictionary with metadata
        """
        schema = cls.model_json_schema()
        schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
        schema['version'] = version
        return schema
