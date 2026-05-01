"""
Intervention Layer (Section 8).

Deterministic interventions based on gate verdicts:
- WARN: log, attach warning header
- THROTTLE: token bucket per edge, capacity scaled inversely to R_team
- ISOLATE: block specific edge
- TERMINATE: block all edges within deadline

WARN/THROTTLE/ISOLATE are reversible after cooldown.
TERMINATE is irreversible for team lifetime.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .config import A2ASTCConfig

logger = logging.getLogger("a2astc.intervention")


class InterventionState(str, Enum):
    """State of an intervention."""

    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    EXPIRED = "EXPIRED"
    PERMANENT = "PERMANENT"


@dataclass
class TokenBucket:
    """Token bucket rate limiter for throttled edges."""

    capacity: float
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)

    def try_consume(self, now: Optional[float] = None) -> bool:
        """Try to consume one token. Returns True if allowed."""
        now = now or time.time()
        self._refill(now)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def _refill(self, now: float) -> None:
        """Refill tokens based on elapsed time."""
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(
                self.capacity, self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now


@dataclass
class Intervention:
    """Record of an applied intervention."""

    intervention_id: str
    verdict: str
    sender_id: str
    receiver_id: str
    team_id: Optional[str]
    manifest_version: Optional[int]
    state: InterventionState
    applied_at: float
    cooldown_until: Optional[float] = None
    reversible: bool = True
    metadata: Dict = field(default_factory=dict)

    @property
    def edge(self) -> Tuple[str, str]:
        """The affected edge."""
        return (self.sender_id, self.receiver_id)

    @property
    def edge_pair(self) -> FrozenSet[str]:
        """The affected edge as undirected pair."""
        return frozenset({self.sender_id, self.receiver_id})


class InterventionLayer:
    """Manages interventions applied by the compliance gate.

    Deterministic: given the same (verdict, edge, manifest_version),
    produces the same intervention. Supports reversible interventions
    with cooldown periods.
    """

    def __init__(self, config: Optional[A2ASTCConfig] = None) -> None:
        self.config = config or A2ASTCConfig()

        # Active interventions keyed by (sender, receiver)
        self._edge_interventions: Dict[Tuple[str, str], Intervention] = {}

        # Terminated teams (irreversible)
        self._terminated_teams: Set[str] = set()

        # Token buckets for throttled edges
        self._token_buckets: Dict[Tuple[str, str], TokenBucket] = {}

        # Isolated edges
        self._isolated_edges: Set[Tuple[str, str]] = set()

        # Intervention history
        self._history: List[Intervention] = []

        # Counter for intervention IDs
        self._counter: int = 0

    def apply(
        self,
        verdict: "Verdict | str",  # type: ignore[name-defined]
        sender_id: str,
        receiver_id: str,
        team_id: Optional[str] = None,
        manifest_version: Optional[int] = None,
        r_team: float = 0.0,
    ) -> Intervention:
        """Apply an intervention based on the gate verdict.

        Args:
            verdict: The gate verdict (WARN, THROTTLE, ISOLATE, TERMINATE).
            sender_id: Sending agent.
            receiver_id: Receiving agent.
            team_id: Team identifier.
            manifest_version: Current manifest version.
            r_team: Current composite risk score.

        Returns:
            The applied Intervention record.
        """
        verdict_str = verdict.value if hasattr(verdict, "value") else str(verdict)
        now = time.time()
        self._counter += 1

        edge = (sender_id, receiver_id)

        if verdict_str == "WARN":
            intervention = self._apply_warn(
                edge, team_id, manifest_version, now
            )
        elif verdict_str == "THROTTLE":
            intervention = self._apply_throttle(
                edge, team_id, manifest_version, now, r_team
            )
        elif verdict_str == "ISOLATE":
            intervention = self._apply_isolate(
                edge, team_id, manifest_version, now
            )
        elif verdict_str == "TERMINATE":
            intervention = self._apply_terminate(
                edge, team_id, manifest_version, now
            )
        else:
            # ALLOW - no intervention
            intervention = Intervention(
                intervention_id=f"int-{self._counter}",
                verdict=verdict_str,
                sender_id=sender_id,
                receiver_id=receiver_id,
                team_id=team_id,
                manifest_version=manifest_version,
                state=InterventionState.EXPIRED,
                applied_at=now,
                reversible=True,
            )

        self._edge_interventions[edge] = intervention
        self._history.append(intervention)
        logger.info(
            "Intervention applied: %s on %s->%s (team=%s)",
            verdict_str,
            sender_id,
            receiver_id,
            team_id,
        )
        return intervention

    def _apply_warn(
        self,
        edge: Tuple[str, str],
        team_id: Optional[str],
        manifest_version: Optional[int],
        now: float,
    ) -> Intervention:
        """Apply WARN intervention - log and attach warning."""
        return Intervention(
            intervention_id=f"int-{self._counter}",
            verdict="WARN",
            sender_id=edge[0],
            receiver_id=edge[1],
            team_id=team_id,
            manifest_version=manifest_version,
            state=InterventionState.ACTIVE,
            applied_at=now,
            cooldown_until=now + self.config.cooldown_interval,
            reversible=True,
        )

    def _apply_throttle(
        self,
        edge: Tuple[str, str],
        team_id: Optional[str],
        manifest_version: Optional[int],
        now: float,
        r_team: float = 0.0,
    ) -> Intervention:
        """Apply THROTTLE intervention - token bucket rate limiting.

        Capacity scales inversely with R_team.
        """
        # Scale capacity: lower risk = more capacity
        scale = max(0.1, 1.0 - r_team)
        capacity = self.config.throttle_bucket_capacity * scale
        refill_rate = self.config.throttle_bucket_refill_rate * scale

        self._token_buckets[edge] = TokenBucket(
            capacity=capacity,
            tokens=capacity,
            refill_rate=refill_rate,
            last_refill=now,
        )

        return Intervention(
            intervention_id=f"int-{self._counter}",
            verdict="THROTTLE",
            sender_id=edge[0],
            receiver_id=edge[1],
            team_id=team_id,
            manifest_version=manifest_version,
            state=InterventionState.ACTIVE,
            applied_at=now,
            cooldown_until=now + self.config.cooldown_interval,
            reversible=True,
            metadata={"capacity": capacity, "refill_rate": refill_rate},
        )

    def _apply_isolate(
        self,
        edge: Tuple[str, str],
        team_id: Optional[str],
        manifest_version: Optional[int],
        now: float,
    ) -> Intervention:
        """Apply ISOLATE intervention - block specific edge."""
        self._isolated_edges.add(edge)

        return Intervention(
            intervention_id=f"int-{self._counter}",
            verdict="ISOLATE",
            sender_id=edge[0],
            receiver_id=edge[1],
            team_id=team_id,
            manifest_version=manifest_version,
            state=InterventionState.ACTIVE,
            applied_at=now,
            cooldown_until=now + self.config.cooldown_interval,
            reversible=True,
        )

    def _apply_terminate(
        self,
        edge: Tuple[str, str],
        team_id: Optional[str],
        manifest_version: Optional[int],
        now: float,
    ) -> Intervention:
        """Apply TERMINATE intervention - block all team edges permanently."""
        if team_id:
            self._terminated_teams.add(team_id)

        # Block this specific edge permanently
        self._isolated_edges.add(edge)

        return Intervention(
            intervention_id=f"int-{self._counter}",
            verdict="TERMINATE",
            sender_id=edge[0],
            receiver_id=edge[1],
            team_id=team_id,
            manifest_version=manifest_version,
            state=InterventionState.PERMANENT,
            applied_at=now,
            cooldown_until=None,
            reversible=False,
        )

    def check_edge(
        self,
        sender_id: str,
        receiver_id: str,
        team_id: Optional[str] = None,
    ) -> Optional[str]:
        """Check if an edge is under active intervention.

        Args:
            sender_id: Sending agent.
            receiver_id: Receiving agent.
            team_id: Team identifier.

        Returns:
            Active verdict string if blocked, None if clear.
        """
        now = time.time()
        edge = (sender_id, receiver_id)

        # Check team termination first
        if team_id and team_id in self._terminated_teams:
            return "TERMINATE"

        # Check edge isolation
        if edge in self._isolated_edges:
            # Check if isolation has cooled down
            intervention = self._edge_interventions.get(edge)
            if intervention:
                if not intervention.reversible:
                    return intervention.verdict
                if (
                    intervention.cooldown_until
                    and now < intervention.cooldown_until
                ):
                    return intervention.verdict
                else:
                    # Cooldown expired, release
                    self._isolated_edges.discard(edge)
                    intervention.state = InterventionState.EXPIRED
                    return None
            return "ISOLATE"

        # Check throttling
        bucket = self._token_buckets.get(edge)
        if bucket:
            intervention = self._edge_interventions.get(edge)
            if intervention and intervention.verdict == "THROTTLE":
                if (
                    intervention.cooldown_until
                    and now >= intervention.cooldown_until
                ):
                    # Cooldown expired
                    del self._token_buckets[edge]
                    intervention.state = InterventionState.EXPIRED
                    return None

                if not bucket.try_consume(now):
                    return "THROTTLE"

        return None

    def release_edge(
        self,
        sender_id: str,
        receiver_id: str,
        force: bool = False,
    ) -> bool:
        """Manually release an edge from intervention.

        Args:
            sender_id: Sending agent.
            receiver_id: Receiving agent.
            force: Force release even if not yet cooled down.

        Returns:
            True if released, False if cannot be released.
        """
        edge = (sender_id, receiver_id)
        intervention = self._edge_interventions.get(edge)

        if not intervention:
            return True

        if not intervention.reversible:
            return False  # TERMINATE cannot be released

        now = time.time()
        if (
            not force
            and intervention.cooldown_until
            and now < intervention.cooldown_until
        ):
            return False  # Still in cooldown

        # Release
        self._isolated_edges.discard(edge)
        self._token_buckets.pop(edge, None)
        intervention.state = InterventionState.EXPIRED
        return True

    def is_team_terminated(self, team_id: str) -> bool:
        """Check if a team has been permanently terminated."""
        return team_id in self._terminated_teams

    def get_active_interventions(self) -> List[Intervention]:
        """Get all currently active interventions."""
        return [
            i
            for i in self._edge_interventions.values()
            if i.state in (InterventionState.ACTIVE, InterventionState.PERMANENT)
        ]

    def get_history(self) -> List[Intervention]:
        """Get full intervention history."""
        return list(self._history)

    def clear(self) -> None:
        """Reset all interventions (for testing)."""
        self._edge_interventions.clear()
        self._terminated_teams.clear()
        self._token_buckets.clear()
        self._isolated_edges.clear()
        self._history.clear()
        self._counter = 0
