from __future__ import annotations

import logging
import random
import time
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Callable, Dict, Optional, Sequence

import dapr.ext.agent_core.mapping
from dapr.ext.agent_core.introspection import detect_framework, find_agent_in_stack
from dapr.ext.agent_core.types import AgentMetadataSchema, SupportedFrameworks
from dapr_agents.agents.configs import (
    AgentRegistryConfig,
)
from dapr_agents.storage.daprstores.stateservice import StateStoreError, StateStoreService

from dapr.clients import DaprClient
from dapr.clients.grpc._response import (
    GetMetadataResponse,
    RegisteredComponents,
)
from dapr.clients.grpc._state import Concurrency, Consistency

logger = logging.getLogger(__name__)


class AgentRegistryAdapter:
    @classmethod
    def create_from_stack(
        cls, registry: Optional[AgentRegistryConfig] = None
    ) -> Optional['AgentRegistryAdapter']:
        """
        Auto-detect and create an AgentRegistryAdapter by walking the call stack.

        Args:
            registry: Optional registry configuration. If None, will attempt auto-discovery.

        Returns:
            AgentRegistryAdapter instance if agent found, None otherwise.
        """
        agent = find_agent_in_stack()
        if not agent:
            return None

        framework = detect_framework(agent)
        if not framework:
            return None

        return cls(registry=registry, framework=framework, agent=agent)

    def __init__(self, registry: Optional[AgentRegistryConfig], framework: str, agent: Any) -> None:
        self._registry = registry

        try:
            with DaprClient(http_timeout_seconds=10) as _client:
                resp: GetMetadataResponse = _client.get_metadata()
                self.appid = resp.application_id
                if self._registry is None:
                    components: Sequence[RegisteredComponents] = resp.registered_components
                    for component in components:
                        if 'state' in component.type and component.name == 'agent-registry':
                            self._registry = AgentRegistryConfig(
                                store=StateStoreService(store_name=component.name),
                                team_name='default',
                            )
        except TimeoutError:
            logger.warning('Dapr sidecar not responding; proceeding without auto-configuration.')

        if self._registry is None:
            return

        self.registry_state: StateStoreService = self._registry.store
        self._registry_prefix: str = 'agents:'
        self._meta: Dict[str, str] = {'contentType': 'application/json'}
        self._max_etag_attempts: int = 10
        self._save_options: Dict[str, Any] = {
            'concurrency': Concurrency.first_write,
            'consistency': Consistency.strong,
        }

        if not self._can_handle(framework):
            raise ValueError(f"Adapter cannot handle framework '{framework}'")

        _metadata = self._extract_metadata(agent)

        # We need to handle some null values here to avoid issues during registration
        if _metadata.agent.appid == '':
            _metadata.agent.appid = self.appid or ''

        if _metadata.registry:
            if _metadata.registry.name is None:
                _metadata.registry.name = self._registry.team_name
            if _metadata.registry.statestore is None:
                _metadata.registry.statestore = self.registry_state.store_name

        self._register(_metadata)

    def _can_handle(self, framework: str) -> bool:
        """Check if this adapter can handle the given Agent."""

        for fw in SupportedFrameworks:
            if framework.lower() == fw.value.lower():
                self._framework = fw
                return True
        return False

    def _extract_metadata(self, agent: Any) -> AgentMetadataSchema:
        """Extract metadata from the given Agent."""

        try:
            schema_version = version('dapr-ext-agent_core')
        except PackageNotFoundError:
            schema_version = 'edge'

        framework_mappers = {
            SupportedFrameworks.DAPR_AGENTS: dapr.ext.agent_core.mapping.DaprAgentsMapper().map_agent_metadata,
            SupportedFrameworks.LANGGRAPH: dapr.ext.agent_core.mapping.LangGraphMapper().map_agent_metadata,
            SupportedFrameworks.STRANDS: dapr.ext.agent_core.mapping.StrandsMapper().map_agent_metadata,
        }

        mapper = framework_mappers.get(self._framework)
        if not mapper:
            raise ValueError(f"Adapter cannot handle framework '{self._framework}'")

        return mapper(agent=agent, schema_version=schema_version)

    def _register(self, metadata: AgentMetadataSchema) -> None:
        """Register the adapter with the given Agent."""
        """
        Upsert this agent's metadata in the team registry.

        Args:
            metadata: Additional metadata to store for this agent.
            team: Team override; falls back to configured default team.
        """
        if not metadata.registry:
            raise ValueError('Registry metadata is required for registration')

        self._upsert_agent_entry(
            team=metadata.registry.name,
            agent_name=metadata.name,
            agent_metadata=metadata.model_dump(),
        )

    def _mutate_registry_entry(
        self,
        *,
        team: Optional[str],
        mutator: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
        max_attempts: Optional[int] = None,
    ) -> None:
        """
        Apply a mutation to the team registry with optimistic concurrency.

        Args:
            team: Team identifier.
            mutator: Function that returns the updated registry dict (or None for no-op).
            max_attempts: Override for concurrency retries; defaults to init value.

        Raises:
            StateStoreError: If the mutation fails after retries due to contention.
        """
        if not self.registry_state:
            raise RuntimeError('registry_state must be provided to mutate the agent registry')

        key = f'agents:{team or "default"}'
        self._meta['partitionKey'] = key
        attempts = max_attempts or self._max_etag_attempts

        self._ensure_registry_initialized(key=key, meta=self._meta)

        for attempt in range(1, attempts + 1):
            logger.debug(f"Mutating registry entry '{key}', attempt {attempt}/{attempts}")
            try:
                current, etag = self.registry_state.load_with_etag(
                    key=key,
                    default={},
                    state_metadata=self._meta,
                )
                if not isinstance(current, dict):
                    current = {}

                updated = mutator(dict(current))
                if updated is None:
                    return

                self.registry_state.save(
                    key=key,
                    value=updated,
                    etag=etag,
                    state_metadata=self._meta,
                    state_options=self._save_options,
                )
                logger.debug(f"Successfully mutated registry entry '{key}'")
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Conflict during registry mutation (attempt %d/%d) for '%s': %s",
                    attempt,
                    attempts,
                    key,
                    exc,
                )
                if attempt == attempts:
                    raise StateStoreError(
                        f"Failed to mutate agent registry key '{key}' after {attempts} attempts."
                    ) from exc
                # Jittered backoff to reduce thundering herd during contention.
                time.sleep(min(1.0 * attempt, 3.0) * (1 + random.uniform(0, 0.25)))

    def _upsert_agent_entry(
        self,
        *,
        team: Optional[str],
        agent_name: str,
        agent_metadata: Dict[str, Any],
        max_attempts: Optional[int] = None,
    ) -> None:
        """
        Insert/update a single agent record in the team registry.

        Args:
            team: Team identifier.
            agent_name: Agent name (key).
            agent_metadata: Metadata value to write.
            max_attempts: Override retry attempts.
        """

        def mutator(current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if current.get(agent_name) == agent_metadata:
                return None
            current[agent_name] = agent_metadata
            return current

        logger.debug("Upserting agent '%s' in team '%s' registry", agent_name, team or 'default')
        self._mutate_registry_entry(
            team=team,
            mutator=mutator,
            max_attempts=max_attempts,
        )

    def _remove_agent_entry(
        self,
        *,
        team: Optional[str],
        agent_name: str,
        max_attempts: Optional[int] = None,
    ) -> None:
        """
        Delete a single agent record from the team registry.

        Args:
            team: Team identifier.
            agent_name: Agent name (key).
            max_attempts: Override retry attempts.
        """

        def mutator(current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if agent_name not in current:
                return None
            del current[agent_name]
            return current

        self._mutate_registry_entry(
            team=team,
            mutator=mutator,
            max_attempts=max_attempts,
        )

    def _ensure_registry_initialized(self, *, key: str, meta: Dict[str, str]) -> None:
        """
        Ensure a registry document exists to create an ETag for concurrency control.

        Args:
            key: Registry document key.
            meta: Dapr state metadata to use for the operation.
        """
        _, etag = self.registry_state.load_with_etag(  # type: ignore[union-attr]
            key=key,
            default={},
            state_metadata=meta,
        )
        if etag is None:
            self.registry_state.save(  # type: ignore[union-attr]
                key=key,
                value={},
                etag=None,
                state_metadata=meta,
                state_options=self._save_options,
            )
