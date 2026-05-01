"""
Deceptive Cascade Detection (Section 6.5).

Detects multi-hop chains where each individual hop appears safe
but the end-to-end chain violates policy:
- Prompt injection propagation across agents
- Goal drift through message transformation
- Policy circumvention via chained operations
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class MessageHop:
    """A single hop in a message chain."""

    sender: str
    receiver: str
    timestamp: float
    content_hash: str
    safety_label: str = "safe"  # per-hop assessment
    transforms: List[str] = field(default_factory=list)


@dataclass
class CascadeChain:
    """A detected multi-hop chain."""

    chain_id: str
    hops: List[MessageHop]
    origin: str
    terminus: str
    total_hops: int
    per_hop_safe: bool  # True if each hop individually rated safe
    end_to_end_safe: bool  # True if the chain result is safe
    is_deceptive: bool  # True if per_hop_safe but not end_to_end_safe

    @property
    def agents_involved(self) -> Set[str]:
        """All unique agents in this chain."""
        agents: Set[str] = set()
        for hop in self.hops:
            agents.add(hop.sender)
            agents.add(hop.receiver)
        return agents


@dataclass
class CascadeSnapshot:
    """Snapshot of cascade analysis metrics."""

    chains_detected: int = 0
    deceptive_chains: int = 0
    max_chain_length: int = 0
    injection_patterns: int = 0
    goal_drift_score: float = 0.0
    risk_score: float = 0.0


class CascadeSignal:
    """Detects deceptive multi-hop cascade patterns.

    Tracks message chains across agents and identifies cases where
    individually-safe hops combine to produce unsafe outcomes.
    """

    def __init__(self, max_chain_depth: int = 10) -> None:
        self._max_chain_depth = max_chain_depth
        # Recent hops indexed by receiver (to build chains)
        self._hops_by_receiver: Dict[str, List[MessageHop]] = defaultdict(list)
        # Recent hops indexed by sender
        self._hops_by_sender: Dict[str, List[MessageHop]] = defaultdict(list)
        # Detected chains
        self._chains: List[CascadeChain] = []
        # Content hash to track transformations
        self._content_evolution: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        # Injection pattern indicators
        self._injection_indicators: List[Tuple[str, str, float]] = []
        _chain_counter = 0

    def record_hop(
        self,
        sender: str,
        receiver: str,
        timestamp: float,
        content_hash: str,
        safety_label: str = "safe",
        transforms: Optional[List[str]] = None,
        input_content_hash: Optional[str] = None,
    ) -> None:
        """Record a message hop for cascade analysis.

        Args:
            sender: Sending agent.
            receiver: Receiving agent.
            timestamp: When the hop occurred.
            content_hash: Hash of the message content.
            safety_label: Per-hop safety assessment ("safe" or "unsafe").
            transforms: List of transformations applied.
            input_content_hash: Hash of the input that generated this output.
        """
        hop = MessageHop(
            sender=sender,
            receiver=receiver,
            timestamp=timestamp,
            content_hash=content_hash,
            safety_label=safety_label,
            transforms=transforms or [],
        )

        self._hops_by_receiver[receiver].append(hop)
        self._hops_by_sender[sender].append(hop)

        # Track content evolution
        if input_content_hash:
            self._content_evolution[input_content_hash].append(
                (content_hash, receiver)
            )

    def record_injection_indicator(
        self,
        agent_id: str,
        pattern_type: str,
        timestamp: float,
    ) -> None:
        """Record a prompt injection indicator observed at an agent."""
        self._injection_indicators.append((agent_id, pattern_type, timestamp))

    def evaluate(self, team_members: Set[str]) -> CascadeSnapshot:
        """Evaluate cascade risk for a team.

        Args:
            team_members: Set of agent IDs to evaluate.

        Returns:
            CascadeSnapshot with analysis results and risk score.
        """
        if len(team_members) < 2:
            return CascadeSnapshot(risk_score=0.0)

        # Build chains from recorded hops
        chains = self._build_chains(team_members)

        # Analyze chains for deceptive patterns
        deceptive_count = 0
        max_length = 0

        for chain in chains:
            if chain.is_deceptive:
                deceptive_count += 1
            max_length = max(max_length, chain.total_hops)

        # Count injection patterns within team
        injection_count = sum(
            1 for agent, _, _ in self._injection_indicators
            if agent in team_members
        )

        # Goal drift score
        goal_drift = self._compute_goal_drift(team_members)

        risk_score = _compute_cascade_risk(
            n_chains=len(chains),
            n_deceptive=deceptive_count,
            max_chain_length=max_length,
            n_injections=injection_count,
            goal_drift=goal_drift,
        )

        return CascadeSnapshot(
            chains_detected=len(chains),
            deceptive_chains=deceptive_count,
            max_chain_length=max_length,
            injection_patterns=injection_count,
            goal_drift_score=goal_drift,
            risk_score=max(0.0, min(1.0, risk_score)),
        )

    def _build_chains(self, team_members: Set[str]) -> List[CascadeChain]:
        """Build message chains by following hop sequences."""
        chains: List[CascadeChain] = []
        chain_counter = 0

        # For each agent, try to trace chains forward
        visited_starts: Set[Tuple[str, int]] = set()

        for sender in team_members:
            sender_hops = self._hops_by_sender.get(sender, [])
            for idx, start_hop in enumerate(sender_hops):
                start_key = (sender, idx)
                if start_key in visited_starts:
                    continue
                visited_starts.add(start_key)

                # Build chain forward
                chain_hops = [start_hop]
                current = start_hop.receiver
                visited_agents: Set[str] = {sender, current}
                depth = 1

                while depth < self._max_chain_depth and current in team_members:
                    # Find next hop from current agent
                    next_hops = [
                        h
                        for h in self._hops_by_sender.get(current, [])
                        if h.timestamp >= chain_hops[-1].timestamp
                        and h.receiver in team_members
                        and h.receiver not in visited_agents
                    ]

                    if not next_hops:
                        break

                    # Take the earliest next hop
                    next_hop = min(next_hops, key=lambda h: h.timestamp)
                    chain_hops.append(next_hop)
                    visited_agents.add(next_hop.receiver)
                    current = next_hop.receiver
                    depth += 1

                if len(chain_hops) >= 2:
                    per_hop_safe = all(
                        h.safety_label == "safe" for h in chain_hops
                    )
                    # End-to-end safety: check if chain origin and terminus
                    # have incompatible safety properties
                    end_to_end_safe = self._assess_chain_safety(chain_hops)

                    chain_counter += 1
                    chain = CascadeChain(
                        chain_id=f"chain-{chain_counter}",
                        hops=chain_hops,
                        origin=chain_hops[0].sender,
                        terminus=chain_hops[-1].receiver,
                        total_hops=len(chain_hops),
                        per_hop_safe=per_hop_safe,
                        end_to_end_safe=end_to_end_safe,
                        is_deceptive=per_hop_safe and not end_to_end_safe,
                    )
                    chains.append(chain)

        self._chains = chains
        return chains

    def _assess_chain_safety(self, hops: List[MessageHop]) -> bool:
        """Assess end-to-end safety of a chain.

        A chain is unsafe end-to-end if:
        - It accumulates too many transforms
        - It contains known injection patterns
        - Content drifts significantly from origin
        """
        total_transforms = sum(len(h.transforms) for h in hops)
        if total_transforms > 5:
            return False

        # Check for injection indicators along the chain
        chain_agents = set()
        for h in hops:
            chain_agents.add(h.sender)
            chain_agents.add(h.receiver)

        injection_in_chain = any(
            agent in chain_agents
            for agent, _, _ in self._injection_indicators
        )
        if injection_in_chain:
            return False

        # Long chains with all transforms are suspicious
        if len(hops) >= 4 and total_transforms >= len(hops):
            return False

        return True

    def _compute_goal_drift(self, team_members: Set[str]) -> float:
        """Compute goal drift score based on content evolution.

        Higher score means more content transformation across hops.
        """
        if not self._content_evolution:
            return 0.0

        total_evolutions = 0
        team_evolutions = 0

        for source_hash, derivatives in self._content_evolution.items():
            for _, agent in derivatives:
                total_evolutions += 1
                if agent in team_members:
                    team_evolutions += 1

        if total_evolutions == 0:
            return 0.0

        # More evolution = more drift
        # Normalize: assume 10+ evolutions within team is high
        return min(1.0, team_evolutions / 10.0)

    def get_chains(self) -> List[CascadeChain]:
        """Get all detected chains."""
        return list(self._chains)

    def clear(self) -> None:
        """Reset all tracked state."""
        self._hops_by_receiver.clear()
        self._hops_by_sender.clear()
        self._chains.clear()
        self._content_evolution.clear()
        self._injection_indicators.clear()


def _compute_cascade_risk(
    n_chains: int,
    n_deceptive: int,
    max_chain_length: int,
    n_injections: int,
    goal_drift: float,
) -> float:
    """Compute composite cascade risk score in [0, 1]."""
    risk = 0.0

    # Deceptive chains are the strongest signal
    if n_deceptive > 0:
        risk += min(0.5, n_deceptive * 0.2)

    # Long chains increase risk
    if max_chain_length >= 5:
        risk += 0.2
    elif max_chain_length >= 3:
        risk += 0.1

    # Injection indicators
    if n_injections > 0:
        risk += min(0.3, n_injections * 0.15)

    # Goal drift
    risk += goal_drift * 0.2

    # Many chains in general
    if n_chains > 5:
        risk += 0.1

    return max(0.0, min(1.0, risk))
