"""
Privilege Aggregation Signals (Section 6.3).

Detects privilege escalation patterns:
- Capability laundering: one agent's output supplies a capability another lacks
- Privilege accumulation across team members
- Role-boundary violations
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CapabilityInvocation:
    """Record of a capability being invoked."""

    agent_id: str
    capability: str
    timestamp: float
    source_agent: Optional[str] = None  # If result came from another agent


@dataclass
class PrivilegeSnapshot:
    """Snapshot of privilege analysis metrics."""

    laundering_chains: List[Tuple[str, str, str]] = field(
        default_factory=list
    )  # (provider, laundered_cap, consumer)
    privilege_concentration: float = 0.0  # Gini coefficient
    boundary_violations: int = 0
    unique_capabilities_used: int = 0
    risk_score: float = 0.0


class PrivilegeSignal:
    """Tracks capability invocations and detects privilege escalation.

    Monitors which agents invoke which capabilities and whether
    capability results are being laundered through intermediary agents.
    """

    def __init__(self) -> None:
        # agent_id -> set of declared capabilities
        self._declared_capabilities: Dict[str, Set[str]] = defaultdict(set)
        # agent_id -> list of capabilities actually invoked
        self._invocations: List[CapabilityInvocation] = []
        # Tracks data flow: (sender, receiver, capability_related)
        self._data_flows: List[Tuple[str, str, str, float]] = []
        # agent_id -> set of capabilities consumed from other agents
        self._consumed_capabilities: Dict[str, Set[str]] = defaultdict(set)

    def declare_capabilities(
        self, agent_id: str, capabilities: Set[str]
    ) -> None:
        """Declare an agent's authorized capabilities."""
        self._declared_capabilities[agent_id] = set(capabilities)

    def record_invocation(
        self,
        agent_id: str,
        capability: str,
        timestamp: float,
        source_agent: Optional[str] = None,
    ) -> None:
        """Record a capability invocation.

        Args:
            agent_id: Agent performing the invocation.
            capability: The capability being invoked.
            timestamp: When the invocation occurred.
            source_agent: If the input/data came from another agent.
        """
        self._invocations.append(
            CapabilityInvocation(
                agent_id=agent_id,
                capability=capability,
                timestamp=timestamp,
                source_agent=source_agent,
            )
        )

    def record_data_flow(
        self,
        sender: str,
        receiver: str,
        capability_context: str,
        timestamp: float,
    ) -> None:
        """Record data flowing from one agent to another in capability context."""
        self._data_flows.append((sender, receiver, capability_context, timestamp))
        self._consumed_capabilities[receiver].add(capability_context)

    def evaluate(self, team_members: Set[str]) -> PrivilegeSnapshot:
        """Evaluate privilege risk for a team.

        Args:
            team_members: Set of agent IDs to evaluate.

        Returns:
            PrivilegeSnapshot with analysis results and risk score.
        """
        if len(team_members) < 2:
            return PrivilegeSnapshot(risk_score=0.0)

        # Detect capability laundering chains
        laundering_chains = self._detect_laundering(team_members)

        # Compute privilege concentration (Gini coefficient of capability usage)
        concentration = self._compute_privilege_concentration(team_members)

        # Detect boundary violations
        violations = self._detect_boundary_violations(team_members)

        # Count unique capabilities used
        unique_caps = set()
        for inv in self._invocations:
            if inv.agent_id in team_members:
                unique_caps.add(inv.capability)

        risk_score = _compute_privilege_risk(
            n_laundering_chains=len(laundering_chains),
            concentration=concentration,
            n_violations=violations,
            n_unique_caps=len(unique_caps),
            n_members=len(team_members),
        )

        return PrivilegeSnapshot(
            laundering_chains=laundering_chains,
            privilege_concentration=concentration,
            boundary_violations=violations,
            unique_capabilities_used=len(unique_caps),
            risk_score=max(0.0, min(1.0, risk_score)),
        )

    def _detect_laundering(
        self, team_members: Set[str]
    ) -> List[Tuple[str, str, str]]:
        """Detect capability laundering chains.

        Laundering occurs when:
        1. Agent A has capability X
        2. Agent B does NOT have capability X
        3. Agent A's output (using X) flows to Agent B
        4. Agent B uses that output to achieve what X would provide
        """
        chains: List[Tuple[str, str, str]] = []

        for sender, receiver, cap, _ in self._data_flows:
            if sender not in team_members or receiver not in team_members:
                continue

            sender_caps = self._declared_capabilities.get(sender, set())
            receiver_caps = self._declared_capabilities.get(receiver, set())

            # If sender has the capability but receiver doesn't,
            # and data flowed from sender to receiver in that context
            if cap in sender_caps and cap not in receiver_caps:
                chains.append((sender, cap, receiver))

        return chains

    def _compute_privilege_concentration(
        self, team_members: Set[str]
    ) -> float:
        """Compute Gini coefficient of capability usage across team."""
        usage_counts: List[int] = []

        for member in team_members:
            count = sum(
                1 for inv in self._invocations if inv.agent_id == member
            )
            usage_counts.append(count)

        return _gini_coefficient(usage_counts)

    def _detect_boundary_violations(self, team_members: Set[str]) -> int:
        """Count invocations where agent uses undeclared capabilities."""
        violations = 0
        for inv in self._invocations:
            if inv.agent_id not in team_members:
                continue
            declared = self._declared_capabilities.get(inv.agent_id, set())
            if declared and inv.capability not in declared:
                violations += 1
        return violations

    def clear(self) -> None:
        """Reset all tracked state."""
        self._declared_capabilities.clear()
        self._invocations.clear()
        self._data_flows.clear()
        self._consumed_capabilities.clear()


def _gini_coefficient(values: List[int]) -> float:
    """Compute Gini coefficient for a list of values.

    Returns 0 (perfect equality) to 1 (perfect inequality).
    """
    if not values or all(v == 0 for v in values):
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)
    total = sum(sorted_values)

    if total == 0:
        return 0.0

    cumulative = 0.0
    gini_sum = 0.0
    for i, val in enumerate(sorted_values):
        cumulative += val
        gini_sum += cumulative

    gini = (2.0 * gini_sum) / (n * total) - (n + 1.0) / n
    return max(0.0, min(1.0, gini))


def _compute_privilege_risk(
    n_laundering_chains: int,
    concentration: float,
    n_violations: int,
    n_unique_caps: int,
    n_members: int,
) -> float:
    """Compute composite privilege risk score in [0, 1]."""
    risk = 0.0

    # Laundering is a strong signal
    if n_laundering_chains > 0:
        risk += min(0.4, n_laundering_chains * 0.15)

    # High concentration (one agent doing everything)
    if concentration > 0.7:
        risk += 0.2
    elif concentration > 0.4:
        risk += 0.1

    # Boundary violations
    if n_violations > 0:
        risk += min(0.3, n_violations * 0.1)

    # Many unique capabilities across few members
    if n_members > 0 and n_unique_caps / max(n_members, 1) > 3:
        risk += 0.15

    return max(0.0, min(1.0, risk))
