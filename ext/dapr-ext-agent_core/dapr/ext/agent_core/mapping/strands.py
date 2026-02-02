from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Any, Optional
from dapr.ext.agent_core.types import (
    AgentMetadata,
    AgentMetadataSchema,
    MemoryMetadata,
    RegistryMetadata,
)

if TYPE_CHECKING:
    from dapr.ext.strands import DaprSessionManager

logger = logging.getLogger(__name__)


class StrandsMapper:
    def __init__(self) -> None:
        pass

    def map_agent_metadata(self, agent: Any, schema_version: str) -> AgentMetadataSchema:
        """
        Map Strands DaprSessionManager to AgentMetadataSchema.
        
        Args:
            agent: The DaprSessionManager instance
            schema_version: Version of the schema
            
        Returns:
            AgentMetadataSchema with extracted metadata
        """
        session_manager: "DaprSessionManager" = agent
        
        # Extract state store name
        state_store_name = getattr(session_manager, '_state_store_name', None)
        session_id = getattr(session_manager, '_session_id', None)
        
        return AgentMetadataSchema(
            schema_version=schema_version,
            agent=AgentMetadata(
                appid="",
                type="Strands",
                orchestrator=False,
                role="Session Manager",
                goal="Manages multi-agent sessions with distributed state storage",
                instructions=[],
                statestore=state_store_name,
                system_prompt=None,
            ),
            name=f"strands-session-{session_id}" if session_id else "strands-session",
            registered_at=datetime.now(timezone.utc).isoformat(),
            pubsub=None,
            memory=MemoryMetadata(
                type="DaprSessionManager",
                session_id=session_id,
                statestore=state_store_name,
            ),
            llm=None,
            registry=RegistryMetadata(
                statestore=None,
                name=None,
            ),
            tools=None,
            max_iterations=None,
            tool_choice=None,
            agent_metadata={
                "framework": "strands",
                "session_id": session_id,
                "state_store": state_store_name,
            },
        )
