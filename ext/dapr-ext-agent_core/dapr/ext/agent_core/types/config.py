from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentRegistryConfig:
    """Configuration for agent registry storage."""

    store_name: str
    team_name: Optional[str] = None