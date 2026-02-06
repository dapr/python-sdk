import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dapr.ext.agent_core.mapping.base import BaseAgentMapper
from dapr.ext.agent_core.types import (
    AgentMetadata,
    AgentMetadataSchema,
    LLMMetadata,
    MemoryMetadata,
    RegistryMetadata,
    ToolMetadata,
)

if TYPE_CHECKING:
    from dapr.ext.strands import DaprSessionManager
    from strands.types.session import SessionAgent

logger = logging.getLogger(__name__)


class StrandsMapper(BaseAgentMapper):
    def __init__(self) -> None:
        pass

    def _is_strands_agent(self, agent: Any) -> bool:
        """Check if agent is an actual Strands Agent (not just session manager)."""
        agent_type = type(agent).__name__
        agent_module = type(agent).__module__
        return agent_type == 'Agent' and 'strands' in agent_module

    def _extract_from_strands_agent(self, agent: Any) -> Dict[str, Any]:
        """Extract metadata from a real Strands Agent.

        Args:
            agent: A strands.Agent instance

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}

        # Basic agent info
        metadata['agent_id'] = getattr(agent, 'agent_id', None) or getattr(agent, 'name', 'agent')
        metadata['name'] = getattr(agent, 'name', None)
        metadata['description'] = getattr(agent, 'description', None)

        # System prompt
        system_prompt = getattr(agent, 'system_prompt', None)
        if system_prompt:
            if isinstance(system_prompt, str):
                metadata['system_prompt'] = system_prompt
            elif isinstance(system_prompt, list):
                # Join list of content blocks
                metadata['system_prompt'] = ' '.join(str(block) for block in system_prompt)

        # Agent state (custom metadata)
        state = getattr(agent, 'state', {})
        try:
            if state:
                # Convert to dict if it's JSONSerializableDict (which doesn't support .get(key, default))
                state_dict = dict(state) if hasattr(state, '__iter__') else {}
                metadata['role'] = state_dict.get('role') or metadata.get('name', 'Agent')
                metadata['goal'] = state_dict.get('goal') or metadata.get('description', '')
                metadata['instructions'] = state_dict.get('instructions') or []
                metadata['max_iterations'] = state_dict.get('max_iterations')
            else:
                metadata['role'] = metadata.get('name', 'Agent')
                metadata['goal'] = metadata.get('description', '')
                metadata['instructions'] = []
        except Exception:
            metadata['role'] = metadata.get('name', 'Agent')
            metadata['goal'] = metadata.get('description', '')
            metadata['instructions'] = []

        # LLM Model
        model = getattr(agent, 'model', None)
        if model:
            model_type = type(model).__name__

            # Check if model has a config
            config = getattr(model, 'config', None)

            # Try multiple possible attribute names for the model ID
            model_id = (
                getattr(model, 'model_id', None)
                or getattr(model, 'model', None)
                or getattr(model, 'name', None)
            )
            if config:
                if isinstance(config, dict) and 'model_id' in config:
                    model_id = config['model_id']
                elif hasattr(config, 'model'):
                    model_id = config.model
                elif hasattr(config, 'model_id'):
                    model_id = config.model_id

            if model_id is None:
                model_id = 'unknown'

            # Extract provider from model module or type
            model_module = type(model).__module__
            provider = self._extract_provider(model_module)

            # Fallback: parse from model type name if provider still unknown
            if provider == 'unknown':
                provider = model_type.replace('Model', '').lower()

            metadata['llm'] = {
                'provider': provider,
                'model': str(model_id),
                'model_type': model_type,
            }

        # Tools - extract from tool_registry.registry
        # In Strands, tools are stored in agent.tool_registry.registry as AgentTool objects
        tools_metadata = []
        tool_registry = getattr(agent, 'tool_registry', None)
        if tool_registry and hasattr(tool_registry, 'registry'):
            registry_dict = tool_registry.registry
            if isinstance(registry_dict, dict):
                for tool_name, agent_tool in registry_dict.items():
                    tool_info = {
                        'name': tool_name,
                        'description': getattr(agent_tool, 'description', '')
                        or getattr(agent_tool, '__doc__', ''),
                    }
                    tools_metadata.append(tool_info)

        metadata['tools'] = tools_metadata

        # Session manager - stored as _session_manager in Strands Agent
        session_manager = getattr(agent, '_session_manager', None)
        if session_manager and type(session_manager).__name__ == 'DaprSessionManager':
            metadata['session_manager'] = session_manager
            metadata['state_store'] = getattr(session_manager, 'state_store_name', None)
            metadata['session_id'] = getattr(session_manager, '_session_id', None)

        return metadata

    def _get_session_agent(
        self, session_manager: 'DaprSessionManager', session_id: str
    ) -> Optional['SessionAgent']:
        """
        Get the primary SessionAgent from a session.

        Reads the session manifest to find agents, and returns the first one.

        Args:
            session_manager: The DaprSessionManager instance
            session_id: Session ID to read from

        Returns:
            SessionAgent if found, None otherwise
        """
        try:
            # Use the session manager's method to get the manifest key
            manifest_key = session_manager._get_manifest_key(session_id)
            logger.info(f'Reading manifest from key: {manifest_key}')
            manifest = session_manager._read_state(manifest_key)

            logger.info(f'Manifest content: {manifest}')

            if not manifest or 'agents' not in manifest or not manifest['agents']:
                logger.warning(
                    f'No agents found in session {session_id} - session may not have agents yet. Use fallback metadata.'
                )
                return None

            # Get the first agent (primary agent)
            agent_id = manifest['agents'][0]
            logger.info(f"Found agent '{agent_id}' in session {session_id}")
            session_agent = session_manager.read_agent(session_id, agent_id)

            if session_agent:
                logger.info(
                    f"Successfully loaded SessionAgent '{agent_id}' with state keys: {list(session_agent.state.keys()) if session_agent.state else []}"
                )
            else:
                logger.warning(f"read_agent returned None for agent_id '{agent_id}'")

            return session_agent

        except Exception as e:
            logger.error(
                f'Failed to read SessionAgent from session {session_id}: {e}', exc_info=True
            )
            return None

    def _extract_llm_metadata(self, agent_state: Dict[str, Any]) -> Optional[LLMMetadata]:
        """
        Extract LLM metadata from SessionAgent state.

        Looks for llm_component, conversation_provider, or llm_config in state.

        Args:
            agent_state: The SessionAgent.state dictionary

        Returns:
            LLMMetadata if LLM configuration found, None otherwise
        """
        # Check for various LLM configuration keys
        llm_component = agent_state.get('llm_component') or agent_state.get('conversation_provider')
        llm_config = agent_state.get('llm_config', {})

        if not llm_component and not llm_config:
            return None

        # Extract LLM details
        provider = llm_config.get('provider', 'unknown')
        model = llm_config.get('model', 'unknown')

        return LLMMetadata(
            client='dapr_conversation',
            provider=provider,
            api='conversation',
            model=model,
            component_name=llm_component,
        )

    def _extract_tools_metadata(self, agent_state: Dict[str, Any]) -> List[ToolMetadata]:
        """
        Extract tools metadata from SessionAgent state.

        Args:
            agent_state: The SessionAgent.state dictionary

        Returns:
            List of ToolMetadata (empty list if no tools configured)
        """
        tools_list = agent_state.get('tools')

        if not tools_list or not isinstance(tools_list, list):
            return []

        tool_metadata_list: List[ToolMetadata] = []
        for tool in tools_list:
            if isinstance(tool, dict):
                tool_metadata_list.append(
                    ToolMetadata(
                        tool_name=str(tool.get('name', 'unknown')),
                        tool_description=str(tool.get('description', '')),
                        tool_args=str(tool.get('args', {})),
                    )
                )
            elif hasattr(tool, 'name'):
                # Handle tool objects
                tool_metadata_list.append(
                    ToolMetadata(
                        tool_name=str(getattr(tool, 'name', 'unknown')),
                        tool_description=str(getattr(tool, 'description', '')),
                        tool_args=str(getattr(tool, 'args', {})),
                    )
                )

        return tool_metadata_list

    def map_agent_metadata(self, agent: Any, schema_version: str) -> AgentMetadataSchema:
        """
        Map Strands Agent or DaprSessionManager to AgentMetadataSchema.

        Handles two cases:
        1. Real Strands Agent (strands.Agent) - extracts from agent properties
        2. DaprSessionManager - extracts from stored SessionAgent in state

        Args:
            agent: Either a strands.Agent or DaprSessionManager instance
            schema_version: Version of the schema

        Returns:
            AgentMetadataSchema with extracted metadata
        """

        # Case 1: Real Strands Agent from the SDK
        if self._is_strands_agent(agent):
            extracted = self._extract_from_strands_agent(agent)

            agent_id = extracted.get('agent_id', 'agent')
            agent_name = extracted.get('name', agent_id)
            session_id = extracted.get('session_id')

            # Build full agent name
            if session_id:
                full_name = f'strands-{session_id}-{agent_id}'
            else:
                full_name = f'strands-{agent_id}'

            # Extract LLM metadata
            llm_info = extracted.get('llm')
            if llm_info:
                llm_metadata = LLMMetadata(
                    client=llm_info.get(
                        'model_type', 'unknown'
                    ),  # OpenAIModel, AnthropicModel, etc.
                    provider=llm_info.get('provider', 'unknown'),  # openai, anthropic, etc.
                    api='chat',  # Strands uses chat-based APIs
                    model=llm_info.get('model', 'unknown'),  # gpt-4o, claude-3-opus, etc.
                    component_name=None,
                )
            else:
                llm_metadata = None

            # Extract tools metadata
            tools_list = extracted.get('tools', [])
            tools_metadata = []
            for tool in tools_list:
                if isinstance(tool, dict):
                    tools_metadata.append(
                        ToolMetadata(
                            tool_name=tool.get('name', 'unknown'),
                            tool_description=tool.get('description', ''),
                            tool_args='',
                        )
                    )

            # Get session manager info for memory and statestore
            state_store_name = extracted.get('state_store')
            session_id_value = extracted.get('session_id')

            # Determine memory type and populate session info
            has_session_manager = extracted.get('session_manager') is not None
            memory_type = 'DaprSessionManager' if has_session_manager else 'InMemory'

            return AgentMetadataSchema(
                schema_version=schema_version,
                agent=AgentMetadata(
                    appid='',
                    type='Strands',
                    orchestrator=False,
                    role=extracted.get('role', agent_name),
                    goal=extracted.get('goal', ''),
                    instructions=extracted.get('instructions')
                    if extracted.get('instructions')
                    else None,
                    statestore=state_store_name,  # Set from session manager
                    system_prompt=extracted.get('system_prompt'),
                ),
                name=full_name,
                registered_at=datetime.now(timezone.utc).isoformat(),
                pubsub=None,
                memory=MemoryMetadata(
                    type=memory_type,
                    session_id=session_id_value,  # Set session_id
                    statestore=state_store_name,  # Set statestore
                ),
                llm=llm_metadata,
                tools=tools_metadata,  # Already a list, could be empty []
                tool_choice='auto'
                if tools_metadata
                else None,  # Set tool_choice based on whether tools exist
                max_iterations=extracted.get('max_iterations'),
                registry=RegistryMetadata(
                    name=None,
                    team='default',
                ),
                agent_metadata={
                    'framework': 'strands',
                    'agent_id': agent_id,
                    'session_id': session_id_value,
                    'state_store': state_store_name,
                },
            )

        # Case 2: DaprSessionManager (legacy approach)
        session_manager: 'DaprSessionManager' = agent

        # Extract session manager info
        state_store_name = getattr(session_manager, 'state_store_name', None)
        session_id = getattr(session_manager, '_session_id', None)

        # Try to get the primary SessionAgent
        session_agent = self._get_session_agent(session_manager, session_id) if session_id else None

        # Extract agent-specific metadata if SessionAgent exists
        if session_agent:
            agent_id = session_agent.agent_id
            agent_state = session_agent.state or {}

            # Extract from state
            system_prompt = agent_state.get('system_prompt')
            role = str(agent_state.get('role', agent_id))
            goal = str(agent_state.get('goal', ''))
            instructions_raw = agent_state.get('instructions', [])
            instructions = list(instructions_raw) if isinstance(instructions_raw, list) else []
            tool_choice = agent_state.get('tool_choice')
            max_iterations = agent_state.get('max_iterations')

            # Extract LLM metadata
            llm_metadata = self._extract_llm_metadata(agent_state)

            # Extract tools metadata
            tools_metadata = self._extract_tools_metadata(agent_state)

            agent_name = f'strands-{session_id}-{agent_id}'
        else:
            # Fallback when no SessionAgent found
            agent_id = None
            agent_state = {}
            system_prompt = None
            role = 'Session Manager'
            goal = 'Manages multi-agent sessions with distributed state storage'
            instructions = []
            tool_choice = None
            max_iterations = None
            llm_metadata = None
            tools_metadata = []
            agent_name = f'strands-session-{session_id}' if session_id else 'strands-session'

        return AgentMetadataSchema(
            schema_version=schema_version,
            agent=AgentMetadata(
                appid='',
                type='Strands',
                orchestrator=False,
                role=role,
                goal=goal,
                instructions=instructions if instructions else None,
                statestore=state_store_name,
                system_prompt=system_prompt,
            ),
            name=agent_name,
            registered_at=datetime.now(timezone.utc).isoformat(),
            pubsub=None,
            memory=MemoryMetadata(
                type='DaprSessionManager',
                statestore=state_store_name,
            ),
            llm=llm_metadata,
            tools=tools_metadata,  # Already a list, could be empty []
            tool_choice=tool_choice,
            max_iterations=max_iterations,
            registry=RegistryMetadata(
                name=None,
                team='default',
            ),
            agent_metadata={
                'framework': 'strands',
                'session_id': session_id,
                'agent_id': agent_id,
                'state_store': state_store_name,
            },
        )
