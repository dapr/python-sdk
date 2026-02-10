import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from dapr.ext.agent_core.metadata.mapping.base import BaseAgentMapper
from dapr.ext.agent_core.types import (
    AgentMetadata,
    AgentMetadataSchema,
    LLMMetadata,
    MemoryMetadata,
    PubSubMetadata,
    RegistryMetadata,
    ToolMetadata,
)
from langgraph.pregel._read import PregelNode

if TYPE_CHECKING:
    from dapr.ext.langgraph import DaprCheckpointer

logger = logging.getLogger(__name__)


class LangGraphMapper(BaseAgentMapper):
    def __init__(self) -> None:
        pass

    def map_agent_metadata(self, agent: Any, schema_version: str) -> AgentMetadataSchema:
        introspected_vars: Dict[str, Any] = vars(agent)  # type: ignore

        nodes: Dict[str, object] = introspected_vars.get('nodes', {})  # type: ignore

        tools: list[Dict[str, Any]] = []
        llm_metadata: Optional[Dict[str, Any]] = None
        system_prompt: Optional[str] = None

        for node_name, obj in nodes.items():  # type: ignore
            if node_name == '__start__':
                # We don't want to process the start node
                continue

            if isinstance(obj, PregelNode):
                node_vars = vars(obj)
                if 'bound' in node_vars.keys():
                    bound = node_vars['bound']

                    # Check if it's a ToolNode
                    if hasattr(bound, '_tools_by_name'):
                        tools_by_name = getattr(bound, '_tools_by_name', {})
                        tools.extend(
                            [
                                {
                                    'name': name,
                                    'description': getattr(tool, 'description', ''),
                                    'args_schema': getattr(
                                        tool, 'args_schema', {}
                                    ),  # TODO: See if we can extract the pydantic model
                                }
                                for name, tool in tools_by_name.items()
                            ]
                        )

                    # Check if it's an assistant RunnableCallable
                    elif type(bound).__name__ == 'RunnableCallable':
                        logger.info(f"Node '{node_name}' is a RunnableCallable")

                        func = getattr(bound, 'func', None)
                        if func and hasattr(func, '__globals__'):
                            func_globals = func.__globals__

                            for _, global_value in func_globals.items():
                                var_type = type(global_value).__name__
                                var_module = type(global_value).__module__

                                if 'chat' in var_type.lower():
                                    model = getattr(global_value, 'model_name', None) or getattr(
                                        global_value, 'model', None
                                    )

                                    if model and not llm_metadata:
                                        llm_metadata = {
                                            'client': var_type,
                                            'provider': self._extract_provider(var_module),
                                            'model': model,
                                            'base_url': getattr(global_value, 'base_url', None),
                                        }

                                # Look for system message
                                elif var_type == 'SystemMessage':
                                    content = getattr(global_value, 'content', None)
                                    if content and not system_prompt:
                                        system_prompt = content

        checkpointer: Optional['DaprCheckpointer'] = introspected_vars.get('checkpointer', None)  # type: ignore

        return AgentMetadataSchema(
            schema_version=schema_version,
            agent=AgentMetadata(
                appid='',
                type=type(agent).__name__,
                orchestrator=False,
                role='Assistant',
                goal=system_prompt or '',
                instructions=[],
                statestore=checkpointer.state_store_name if checkpointer else None,  # type: ignore
                system_prompt='',
                framework='LangGraph',
            ),
            name=agent.get_name() if hasattr(agent, 'get_name') else '',
            registered_at=datetime.now(timezone.utc).isoformat(),
            pubsub=PubSubMetadata(
                name='',
                broadcast_topic=None,
                agent_topic=None,
            ),
            memory=MemoryMetadata(
                type='DaprCheckpointer',
                statestore=checkpointer.state_store_name if checkpointer else None,  # type: ignore
            ),
            llm=LLMMetadata(
                client=llm_metadata.get('client', '') if llm_metadata else '',
                provider=llm_metadata.get('provider', 'unknown') if llm_metadata else 'unknown',
                api='chat',
                model=llm_metadata.get('model', 'unknown') if llm_metadata else 'unknown',
                component_name=None,
                base_url=llm_metadata.get('base_url') if llm_metadata else None,
                azure_endpoint=llm_metadata.get('azure_endpoint') if llm_metadata else None,
                azure_deployment=llm_metadata.get('azure_deployment') if llm_metadata else None,
                prompt_template=None,
            ),
            registry=RegistryMetadata(
                statestore=None,
                name=None,
            ),
            tools=[
                ToolMetadata(
                    tool_name=tool.get('name', ''),
                    tool_description=tool.get('description', ''),
                    tool_args='',
                )
                for tool in tools
            ],
            max_iterations=1,
            tool_choice='auto',
            agent_metadata=None,
        )
