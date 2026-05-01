"""
Team Detection (Section 4).

Tracks agent-to-agent communication edges in a sliding window and forms
teams when bidirectional pairs are detected.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .config import A2ASTCConfig

logger = logging.getLogger("a2astc.detector")


@dataclass
class Edge:
    """A directed communication edge between two agents."""

    sender_id: str
    receiver_id: str
    timestamp: float

    @property
    def pair(self) -> FrozenSet[str]:
        """Return the undirected pair for this edge."""
        return frozenset({self.sender_id, self.receiver_id})


@dataclass
class Team:
    """A detected team of collaborating agents."""

    team_id: str
    members: Set[str] = field(default_factory=set)
    formed_at: float = field(default_factory=time.time)
    pairs: Set[FrozenSet[str]] = field(default_factory=set)
    dissolved: bool = False
    dissolved_at: Optional[float] = None

    def has_member(self, agent_id: str) -> bool:
        """Check if an agent is a member of this team."""
        return agent_id in self.members


def _generate_team_id() -> str:
    """Generate a unique team identifier.

    Attempts UUIDv7 for time-ordered IDs, falls back to UUIDv4.
    """
    try:
        return str(uuid.uuid7())  # type: ignore[attr-defined]
    except AttributeError:
        try:
            import uuid6  # type: ignore[import-untyped]
            return str(uuid6.uuid7())
        except ImportError:
            return str(uuid.uuid4())


class TeamDetector:
    """Detects emergent teams from agent-to-agent communication patterns.

    Maintains a sliding window of communication edges and forms teams
    when bidirectional communication pairs are detected. Teams grow
    when new pairs share members with existing teams, and merge when
    a pair links two separate teams.
    """

    def __init__(self, config: Optional[A2ASTCConfig] = None) -> None:
        self.config = config or A2ASTCConfig()
        self.pending_edges: List[Edge] = []
        self.active_pairs: Set[FrozenSet[str]] = set()
        self.teams: Dict[str, Team] = {}
        self._direction_map: Dict[Tuple[str, str], float] = {}

    def observe_edge(
        self,
        sender_id: str,
        receiver_id: str,
        timestamp: Optional[float] = None,
    ) -> Optional[str]:
        """Record a directed communication edge and detect/update teams.

        Args:
            sender_id: The sending agent's identifier.
            receiver_id: The receiving agent's identifier.
            timestamp: Edge timestamp (defaults to current time).

        Returns:
            team_id if a team was formed, grown, or merged; None otherwise.
        """
        if sender_id == receiver_id:
            logger.debug("Ignoring self-loop edge: %s", sender_id)
            return None

        ts = timestamp if timestamp is not None else time.time()
        edge = Edge(sender_id=sender_id, receiver_id=receiver_id, timestamp=ts)

        # Expire old edges
        self._expire_edges(ts)

        # Record the directed edge
        self.pending_edges.append(edge)
        self._direction_map[(sender_id, receiver_id)] = ts

        # Check if bidirectional pair now exists
        reverse_key = (receiver_id, sender_id)
        if reverse_key in self._direction_map:
            reverse_ts = self._direction_map[reverse_key]
            if ts - reverse_ts <= self.config.team_window:
                pair = edge.pair
                if pair not in self.active_pairs:
                    self.active_pairs.add(pair)
                    return self._integrate_pair(pair, ts)
                else:
                    # Pair already active, find its team
                    for team in self.teams.values():
                        if not team.dissolved and pair in team.pairs:
                            return team.team_id
        return None

    def _expire_edges(self, now: float) -> None:
        """Remove edges outside the sliding window."""
        cutoff = now - self.config.team_window

        # Expire pending edges
        self.pending_edges = [e for e in self.pending_edges if e.timestamp > cutoff]

        # Expire direction map entries
        expired_keys = [
            k for k, ts in self._direction_map.items() if ts <= cutoff
        ]
        for k in expired_keys:
            del self._direction_map[k]

        # Expire pairs whose edges are both gone
        expired_pairs: Set[FrozenSet[str]] = set()
        for pair in self.active_pairs:
            agents = list(pair)
            if len(agents) != 2:
                continue
            a, b = agents[0], agents[1]
            fwd_alive = (a, b) in self._direction_map
            rev_alive = (b, a) in self._direction_map
            if not (fwd_alive and rev_alive):
                expired_pairs.add(pair)

        for pair in expired_pairs:
            self.active_pairs.discard(pair)
            self._remove_pair_from_teams(pair, now)

    def _integrate_pair(self, pair: FrozenSet[str], timestamp: float) -> str:
        """Integrate a new bidirectional pair into team structures.

        Handles team formation, growth, and merging.
        """
        agents = list(pair)
        a, b = agents[0], agents[1]

        # Find teams that contain either agent
        matching_teams: List[str] = []
        for team_id, team in self.teams.items():
            if team.dissolved:
                continue
            if team.has_member(a) or team.has_member(b):
                matching_teams.append(team_id)

        if len(matching_teams) == 0:
            # Form new team
            team_id = _generate_team_id()
            team = Team(
                team_id=team_id,
                members={a, b},
                formed_at=timestamp,
                pairs={pair},
            )
            self.teams[team_id] = team
            logger.info("Team formed: %s with members {%s, %s}", team_id, a, b)
            return team_id

        elif len(matching_teams) == 1:
            # Grow existing team
            team = self.teams[matching_teams[0]]
            team.members.add(a)
            team.members.add(b)
            team.pairs.add(pair)
            logger.info("Team grown: %s now has %d members", team.team_id, len(team.members))
            return team.team_id

        else:
            # Merge teams
            primary = self.teams[matching_teams[0]]
            for other_id in matching_teams[1:]:
                other = self.teams[other_id]
                primary.members.update(other.members)
                primary.pairs.update(other.pairs)
                other.dissolved = True
                other.dissolved_at = timestamp
                logger.info("Team merged: %s absorbed %s", primary.team_id, other_id)

            primary.members.add(a)
            primary.members.add(b)
            primary.pairs.add(pair)
            return primary.team_id

    def _remove_pair_from_teams(self, pair: FrozenSet[str], now: float) -> None:
        """Remove an expired pair from teams and dissolve if below min size."""
        for team in list(self.teams.values()):
            if team.dissolved:
                continue
            if pair in team.pairs:
                team.pairs.discard(pair)
                # Recompute members from remaining pairs
                remaining_members: Set[str] = set()
                for p in team.pairs:
                    remaining_members.update(p)
                team.members = remaining_members

                if len(team.members) < self.config.min_team_size:
                    team.dissolved = True
                    team.dissolved_at = now
                    logger.info("Team dissolved: %s (below min size)", team.team_id)

    def remove_agent(self, agent_id: str, timestamp: Optional[float] = None) -> List[str]:
        """Remove an agent from all teams.

        Args:
            agent_id: The agent to remove.
            timestamp: Removal timestamp (defaults to current time).

        Returns:
            List of team_ids affected.
        """
        now = timestamp if timestamp is not None else time.time()
        affected: List[str] = []

        for team in list(self.teams.values()):
            if team.dissolved:
                continue
            if agent_id not in team.members:
                continue

            affected.append(team.team_id)
            # Remove all pairs involving this agent
            agent_pairs = {p for p in team.pairs if agent_id in p}
            team.pairs -= agent_pairs
            team.members.discard(agent_id)

            # Remove from active_pairs too
            for p in agent_pairs:
                self.active_pairs.discard(p)

            # Recompute members
            remaining: Set[str] = set()
            for p in team.pairs:
                remaining.update(p)
            team.members = remaining

            if len(team.members) < self.config.min_team_size:
                team.dissolved = True
                team.dissolved_at = now
                logger.info("Team dissolved after agent removal: %s", team.team_id)

        # Clean direction map
        keys_to_remove = [
            k for k in self._direction_map
            if k[0] == agent_id or k[1] == agent_id
        ]
        for k in keys_to_remove:
            del self._direction_map[k]

        return affected

    def get_team(self, team_id: str) -> Optional[Team]:
        """Get a team by its identifier."""
        return self.teams.get(team_id)

    def get_teams_for_agent(self, agent_id: str) -> List[Team]:
        """Get all active teams an agent belongs to."""
        return [
            t for t in self.teams.values()
            if not t.dissolved and agent_id in t.members
        ]

    def get_active_teams(self) -> List[Team]:
        """Get all currently active (non-dissolved) teams."""
        return [t for t in self.teams.values() if not t.dissolved]

    def get_team_for_edge(self, sender_id: str, receiver_id: str) -> Optional[Team]:
        """Find the active team that contains a given edge."""
        pair = frozenset({sender_id, receiver_id})
        for team in self.teams.values():
            if not team.dissolved and pair in team.pairs:
                return team
        return None
