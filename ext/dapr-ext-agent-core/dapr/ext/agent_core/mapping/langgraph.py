
from datetime import datetime, timezone
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional
from dapr.ext.agent_core.types import AgentMetadata, AgentMetadataSchema, LLMMetadata, MemoryMetadata, PubSubMetadata, RegistryMetadata, ToolMetadata

if TYPE_CHECKING:
    from dapr.ext.langgraph import DaprCheckpointer

logger = logging.getLogger(__name__)

class LangGraphMapper:
    def __init__(self) -> None:
        pass

    def map_agent_metadata(self, agent: Any, schema_version: str) -> AgentMetadataSchema:

        logger.info(f"LangGraph log vars: {vars(agent)}")
        print(f"LangGraph print vars: {vars(agent)}")
        logger.info(f"LangGraph log dir: {dir(agent)}")
        print(f"LangGraph print dir: {dir(agent)}")

        introspected_vars: Dict[str, Any] = vars(agent) # type: ignore
        introspected_dir = dir(agent)

        checkpointer: Optional["DaprCheckpointer"] = introspected_vars.get("checkpointer", None) # type: ignore
        tools = introspected_vars.get("tools", []) # type: ignore
        print(f"LangGraph tools: {tools}")

        return AgentMetadataSchema(
            schema_version=schema_version,
            agent=AgentMetadata(
                appid="",
                type=type(agent).__name__,
                orchestrator=False,
                role="",
                goal="",
                instructions=[],
                statestore=checkpointer.store_name if checkpointer else None,
                system_prompt="",
            ),
            name=agent.get_name() if hasattr(agent, "get_name") else "",
            registered_at=datetime.now(timezone.utc).isoformat(),
            pubsub=PubSubMetadata(
                name="",
                broadcast_topic=None,
                agent_topic=None,
            ),
            memory=MemoryMetadata(
                type="DaprCheckpointer",
                session_id=None,
                statestore=checkpointer.store_name if checkpointer else None,
            ),
            llm=LLMMetadata(
                client="",
                provider="unknown",
                api="unknown",
                model="unknown",
                component_name=None,
                base_url=None,
                azure_endpoint=None,
                azure_deployment=None,
                prompt_template=None,
            ),
            registry=RegistryMetadata(
                statestore=None,
                name=None,
            ),
            tools=[
                ToolMetadata(
                    tool_name="",
                    tool_description="",
                    tool_args=json.dumps({})
                    if hasattr(tool, "args_schema") else "{}",
                )
                for tool in getattr(agent, "tools", [])
            ],
            max_iterations=None,
            tool_choice=None,
            agent_metadata=None,
        )
