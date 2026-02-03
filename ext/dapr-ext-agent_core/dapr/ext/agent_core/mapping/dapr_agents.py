import gc
import json
import logging
from datetime import datetime, timezone
from typing import Any

from dapr.ext.agent_core.mapping.base import BaseAgentMapper
from dapr.ext.agent_core.types import (
    AgentMetadata,
    AgentMetadataSchema,
    LLMMetadata,
    MemoryMetadata,
    PubSubMetadata,
    RegistryMetadata,
    ToolMetadata,
)

logger = logging.getLogger(__name__)


class DaprAgentsMapper(BaseAgentMapper):
    def __init__(self) -> None:
        pass

    def map_agent_metadata(self, agent: Any, schema_version: str) -> AgentMetadataSchema:
        # If we received a base class (DaprInfra, AgentBase), try to find the actual derived agent via GC
        agent_type = type(agent).__name__
        if agent_type in ('DaprInfra', 'AgentBase'):
            referrers = gc.get_referrers(agent)
            for ref in referrers:
                ref_type = type(ref).__name__
                ref_module = type(ref).__module__
                # Look for derived agent classes in dapr_agents module
                if 'dapr_agents' in ref_module and ref_type not in ('DaprInfra', 'AgentBase'):
                    agent = ref
                    break

        profile = getattr(agent, 'profile', None)
        memory = getattr(agent, 'memory', None)
        pubsub = getattr(agent, 'pubsub', None)
        llm = getattr(agent, 'llm', None)
        registry = getattr(agent, '_registry', None)
        execution = getattr(agent, 'execution', None)

        return AgentMetadataSchema(
            schema_version=schema_version,
            agent=AgentMetadata(
                appid=getattr(agent, 'appid', ''),
                type=type(agent).__name__,
                orchestrator=False,
                role=getattr(profile, 'role', '') if profile else '',
                goal=getattr(profile, 'goal', '') if profile else '',
                instructions=getattr(profile, 'instructions', None) if profile else [],
                statestore=getattr(memory, 'store_name', '') if memory else '',
                system_prompt=getattr(profile, 'system_prompt', '') if profile else '',
            ),
            name=getattr(agent, 'name', ''),
            registered_at=datetime.now(timezone.utc).isoformat(),
            pubsub=PubSubMetadata(
                name=getattr(pubsub, 'pubsub_name', '') if pubsub else '',
                broadcast_topic=getattr(pubsub, 'broadcast_topic', None) if pubsub else None,
                agent_topic=getattr(pubsub, 'agent_topic', None) if pubsub else None,
            ),
            memory=MemoryMetadata(
                type=type(memory).__name__ if memory else '',
                session_id=getattr(memory, 'session_id', None) if memory else None,
                statestore=getattr(memory, 'store_name', None) if memory else None,
            ),
            llm=LLMMetadata(
                client=type(llm).__name__ if llm else '',
                provider=getattr(llm, 'provider', 'unknown') if llm else 'unknown',
                api=getattr(llm, 'api', 'unknown') if llm else 'unknown',
                model=getattr(llm, 'model', 'unknown') if llm else 'unknown',
                component_name=getattr(llm, 'component_name', None) if llm else None,
                base_url=getattr(llm, 'base_url', None) if llm else None,
                azure_endpoint=getattr(llm, 'azure_endpoint', None) if llm else None,
                azure_deployment=getattr(llm, 'azure_deployment', None) if llm else None,
                prompt_template=type(getattr(llm, 'prompt_template', None)).__name__
                if llm and getattr(llm, 'prompt_template', None)
                else None,
            ),
            registry=RegistryMetadata(
                statestore=getattr(getattr(registry, 'store', None), 'store_name', None)
                if registry
                else None,
                name=getattr(registry, 'team_name', None) if registry else None,
            ),
            tools=[
                ToolMetadata(
                    tool_name=getattr(tool, 'name', ''),
                    tool_description=getattr(tool, 'description', ''),
                    tool_args=json.dumps(getattr(tool, 'args_schema', {}))
                    if hasattr(tool, 'args_schema')
                    else '{}',
                )
                for tool in getattr(agent, 'tools', [])
            ],
            max_iterations=getattr(execution, 'max_iterations', None) if execution else None,
            tool_choice=getattr(execution, 'tool_choice', None) if execution else None,
            agent_metadata=getattr(agent, 'agent_metadata', None),
        )
