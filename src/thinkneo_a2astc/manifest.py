"""
Team Manifest (Section 5).

Immutable-versioned manifest describing a detected team, its members,
aggregate capabilities, and escalation classification.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set

from .config import A2ASTCConfig


class TeamState(str, Enum):
    """Team lifecycle states."""

    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    THROTTLED = "THROTTLED"
    ISOLATED = "ISOLATED"
    TERMINATED = "TERMINATED"
    DISSOLVED = "DISSOLVED"


class SafetyClass(str, Enum):
    """Aggregate safety classification for a team."""

    STANDARD = "STANDARD"
    RESTRICTED = "RESTRICTED"
    HIGH_RISK = "HIGH_RISK"


@dataclass
class MemberRecord:
    """Record for a single team member agent."""

    agent_id: str
    provider: str = "unknown"
    model_class: str = "unknown"
    capabilities: Set[str] = field(default_factory=set)
    joined_ts: float = field(default_factory=time.time)
    role_inferred: str = "peer"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "provider": self.provider,
            "model_class": self.model_class,
            "capabilities": sorted(self.capabilities),
            "joined_ts": self.joined_ts,
            "role_inferred": self.role_inferred,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemberRecord":
        """Deserialize from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            provider=data.get("provider", "unknown"),
            model_class=data.get("model_class", "unknown"),
            capabilities=set(data.get("capabilities", [])),
            joined_ts=data.get("joined_ts", time.time()),
            role_inferred=data.get("role_inferred", "peer"),
        )


@dataclass
class TeamManifest:
    """Versioned manifest for a detected agent team.

    Tracks members, aggregate capabilities, safety classification,
    and team state with a monotonically increasing version counter.
    """

    team_id: str
    members: Dict[str, MemberRecord] = field(default_factory=dict)
    state: TeamState = TeamState.FORMING
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    aggregate_capabilities: Set[str] = field(default_factory=set)
    safety_class: SafetyClass = SafetyClass.STANDARD
    metadata: Dict[str, Any] = field(default_factory=dict)

    _config: Optional[A2ASTCConfig] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._config is None:
            self._config = A2ASTCConfig()

    def _bump_version(self) -> None:
        """Increment the manifest version (monotonic)."""
        self.version += 1
        self.updated_at = time.time()

    def add_member(
        self,
        agent_id: str,
        provider: str = "unknown",
        model_class: str = "unknown",
        capabilities: Optional[Set[str]] = None,
        role_inferred: str = "peer",
        joined_ts: Optional[float] = None,
    ) -> MemberRecord:
        """Add or update a member in the manifest.

        Recomputes aggregate capabilities and safety class.
        """
        member = MemberRecord(
            agent_id=agent_id,
            provider=provider,
            model_class=model_class,
            capabilities=capabilities or set(),
            joined_ts=joined_ts if joined_ts is not None else time.time(),
            role_inferred=role_inferred,
        )
        self.members[agent_id] = member
        self._recompute_aggregates()
        self._bump_version()

        if self.state == TeamState.FORMING and len(self.members) >= 2:
            self.state = TeamState.ACTIVE

        return member

    def remove_member(self, agent_id: str) -> Optional[MemberRecord]:
        """Remove a member from the manifest.

        Recomputes aggregates and may dissolve the team.
        """
        member = self.members.pop(agent_id, None)
        if member is not None:
            self._recompute_aggregates()
            self._bump_version()

            min_size = self._config.min_team_size if self._config else 2
            if len(self.members) < min_size:
                self.state = TeamState.DISSOLVED
        return member

    def _recompute_aggregates(self) -> None:
        """Recompute aggregate capabilities and safety classification."""
        self.aggregate_capabilities = set()
        for member in self.members.values():
            self.aggregate_capabilities.update(member.capabilities)

        self.safety_class = self._classify_safety()

    def _classify_safety(self) -> SafetyClass:
        """Classify the team's aggregate safety level.

        Checks escalation pairs and high-risk thresholds.
        """
        config = self._config or A2ASTCConfig()
        caps = self.aggregate_capabilities

        # Check escalation pairs for RESTRICTED
        for pair_set, classification in config.escalation_pairs:
            if pair_set.issubset(caps):
                if classification == "HIGH_RISK":
                    return SafetyClass.HIGH_RISK
                # At least RESTRICTED
                result = SafetyClass.RESTRICTED

        # Check high-risk threshold (any 3 of 4 categories)
        matching_categories = sum(
            1 for cat in config.high_risk_categories if cat in caps
        )
        if matching_categories >= config.high_risk_threshold:
            return SafetyClass.HIGH_RISK

        # Check for RESTRICTED from escalation pairs
        for pair_set, classification in config.escalation_pairs:
            if pair_set.issubset(caps):
                return SafetyClass.RESTRICTED

        return SafetyClass.STANDARD

    def set_state(self, new_state: TeamState) -> None:
        """Transition team to a new state."""
        # Validate transitions
        if self.state == TeamState.TERMINATED and new_state != TeamState.DISSOLVED:
            raise ValueError(
                f"Cannot transition from TERMINATED to {new_state}; "
                "TERMINATED is irreversible within team lifetime"
            )
        if self.state == TeamState.DISSOLVED:
            raise ValueError("Cannot transition from DISSOLVED state")

        self.state = new_state
        self._bump_version()

    def get_member_capabilities(self, agent_id: str) -> Set[str]:
        """Get capabilities for a specific member."""
        member = self.members.get(agent_id)
        return member.capabilities if member else set()

    def get_member_ids(self) -> List[str]:
        """Get all member agent IDs."""
        return list(self.members.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the manifest to a dictionary."""
        return {
            "team_id": self.team_id,
            "members": {
                agent_id: member.to_dict()
                for agent_id, member in self.members.items()
            },
            "state": self.state.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "aggregate_capabilities": sorted(self.aggregate_capabilities),
            "safety_class": self.safety_class.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        config: Optional[A2ASTCConfig] = None,
    ) -> "TeamManifest":
        """Deserialize from a dictionary."""
        manifest = cls(
            team_id=data["team_id"],
            state=TeamState(data.get("state", "FORMING")),
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            aggregate_capabilities=set(data.get("aggregate_capabilities", [])),
            safety_class=SafetyClass(data.get("safety_class", "STANDARD")),
            metadata=data.get("metadata", {}),
            _config=config,
        )

        for agent_id, member_data in data.get("members", {}).items():
            manifest.members[agent_id] = MemberRecord.from_dict(member_data)

        return manifest
