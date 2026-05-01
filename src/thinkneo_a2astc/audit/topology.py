"""
Communication Topology Signals (Section 6.1).

Analyzes the communication graph structure to detect anomalous patterns:
- Edge density relative to maximum
- In/out-degree distribution skew
- Clustering coefficient
- Topology classification (star, ring, mesh, hierarchical)
- Sub-coalition detection via community detection
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


@dataclass
class TopologySnapshot:
    """Snapshot of topology metrics at a point in time."""

    edge_density: float = 0.0
    max_in_degree: int = 0
    max_out_degree: int = 0
    degree_skew: float = 0.0
    clustering_coefficient: float = 0.0
    topology_type: str = "unknown"
    sub_coalitions: List[Set[str]] = field(default_factory=list)
    risk_score: float = 0.0


class TopologySignal:
    """Analyzes communication graph topology for risk signals.

    Tracks directed edges between agents and computes structural
    metrics that indicate anomalous collaboration patterns.
    """

    def __init__(self) -> None:
        self._edges: List[Tuple[str, str, float]] = []
        self._adjacency_out: Dict[str, Set[str]] = defaultdict(set)
        self._adjacency_in: Dict[str, Set[str]] = defaultdict(set)
        self._undirected: Dict[str, Set[str]] = defaultdict(set)

    def record_edge(self, sender: str, receiver: str, timestamp: float) -> None:
        """Record a directed communication edge."""
        self._edges.append((sender, receiver, timestamp))
        self._adjacency_out[sender].add(receiver)
        self._adjacency_in[receiver].add(sender)
        self._undirected[sender].add(receiver)
        self._undirected[receiver].add(sender)

    def clear(self) -> None:
        """Reset all recorded edges."""
        self._edges.clear()
        self._adjacency_out.clear()
        self._adjacency_in.clear()
        self._undirected.clear()

    def evaluate(self, team_members: Set[str]) -> TopologySnapshot:
        """Evaluate topology risk for a given set of team members.

        Args:
            team_members: Set of agent IDs in the team.

        Returns:
            TopologySnapshot with computed metrics and risk score.
        """
        n = len(team_members)
        if n < 2:
            return TopologySnapshot(risk_score=0.0)

        # Filter edges to team members only
        team_out: Dict[str, Set[str]] = defaultdict(set)
        team_in: Dict[str, Set[str]] = defaultdict(set)
        team_undirected: Dict[str, Set[str]] = defaultdict(set)

        edge_count = 0
        for sender, receiver, _ in self._edges:
            if sender in team_members and receiver in team_members:
                team_out[sender].add(receiver)
                team_in[receiver].add(sender)
                team_undirected[sender].add(receiver)
                team_undirected[receiver].add(sender)
                edge_count += 1

        # Edge density: actual edges / maximum possible directed edges
        max_edges = n * (n - 1)
        edge_density = edge_count / max_edges if max_edges > 0 else 0.0

        # Degree statistics
        out_degrees = [len(team_out.get(m, set())) for m in team_members]
        in_degrees = [len(team_in.get(m, set())) for m in team_members]

        max_out = max(out_degrees) if out_degrees else 0
        max_in = max(in_degrees) if in_degrees else 0

        # Degree skew: normalized std deviation of total degree
        total_degrees = [
            len(team_out.get(m, set())) + len(team_in.get(m, set()))
            for m in team_members
        ]
        degree_skew = _normalized_std(total_degrees)

        # Clustering coefficient (undirected)
        clustering = _average_clustering(team_members, team_undirected)

        # Topology classification
        topology_type = _classify_topology(
            n, edge_density, degree_skew, max_out, max_in, total_degrees
        )

        # Sub-coalition detection
        sub_coalitions = _detect_sub_coalitions(team_members, team_undirected)

        # Composite risk score
        risk_score = _compute_topology_risk(
            edge_density=edge_density,
            degree_skew=degree_skew,
            clustering=clustering,
            topology_type=topology_type,
            n_sub_coalitions=len(sub_coalitions),
            n_members=n,
        )

        return TopologySnapshot(
            edge_density=edge_density,
            max_in_degree=max_in,
            max_out_degree=max_out,
            degree_skew=degree_skew,
            clustering_coefficient=clustering,
            topology_type=topology_type,
            sub_coalitions=sub_coalitions,
            risk_score=max(0.0, min(1.0, risk_score)),
        )


def _normalized_std(values: List[int]) -> float:
    """Compute standard deviation normalized to [0, 1] range."""
    if not values or len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    max_val = max(values)
    return std / max_val if max_val > 0 else 0.0


def _average_clustering(
    members: Set[str], adjacency: Dict[str, Set[str]]
) -> float:
    """Compute average clustering coefficient for undirected graph."""
    if len(members) < 3:
        return 0.0

    coefficients: List[float] = []
    for node in members:
        neighbors = adjacency.get(node, set()) & members
        k = len(neighbors)
        if k < 2:
            coefficients.append(0.0)
            continue

        # Count edges among neighbors
        neighbor_edges = 0
        neighbor_list = list(neighbors)
        for i in range(len(neighbor_list)):
            for j in range(i + 1, len(neighbor_list)):
                if neighbor_list[j] in adjacency.get(neighbor_list[i], set()):
                    neighbor_edges += 1

        max_neighbor_edges = k * (k - 1) / 2
        coefficients.append(
            neighbor_edges / max_neighbor_edges if max_neighbor_edges > 0 else 0.0
        )

    return sum(coefficients) / len(coefficients) if coefficients else 0.0


def _classify_topology(
    n: int,
    edge_density: float,
    degree_skew: float,
    max_out: int,
    max_in: int,
    total_degrees: List[int],
) -> str:
    """Classify the communication topology pattern."""
    if n < 2:
        return "degenerate"

    # Star: one node with very high degree, others with degree ~1
    if degree_skew > 0.6 and (max_out >= n - 1 or max_in >= n - 1):
        return "star"

    # Mesh: high density, low skew
    if edge_density > 0.7 and degree_skew < 0.3:
        return "mesh"

    # Ring: each node has degree ~2
    if n >= 3:
        avg_degree = sum(total_degrees) / len(total_degrees) if total_degrees else 0
        if 1.5 <= avg_degree <= 2.5 and degree_skew < 0.2:
            return "ring"

    # Hierarchical: moderate density, moderate skew
    if 0.3 < edge_density < 0.7 and degree_skew > 0.3:
        return "hierarchical"

    return "unclassified"


def _detect_sub_coalitions(
    members: Set[str], adjacency: Dict[str, Set[str]]
) -> List[Set[str]]:
    """Detect sub-coalitions using simple connected component analysis.

    For small teams, finds connected components that form tight sub-groups.
    Uses a simple label propagation approach.
    """
    if len(members) < 3:
        return []

    # Find connected components
    visited: Set[str] = set()
    components: List[Set[str]] = []

    for start in members:
        if start in visited:
            continue
        component: Set[str] = set()
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            neighbors = adjacency.get(node, set()) & members
            for nb in neighbors:
                if nb not in visited:
                    queue.append(nb)
        if len(component) >= 2:
            components.append(component)

    # If there's more than one component, those are distinct sub-coalitions
    if len(components) > 1:
        return components

    # For a single connected component, try to find densely connected sub-groups
    # using degree-based heuristic: nodes with above-average internal degree
    if len(components) == 1 and len(members) >= 4:
        component = components[0]
        avg_degree = sum(
            len(adjacency.get(m, set()) & members) for m in component
        ) / len(component)

        high_degree = {
            m for m in component
            if len(adjacency.get(m, set()) & members) > avg_degree
        }
        low_degree = component - high_degree

        if len(high_degree) >= 2 and len(low_degree) >= 2:
            return [high_degree, low_degree]

    return []


def _compute_topology_risk(
    edge_density: float,
    degree_skew: float,
    clustering: float,
    topology_type: str,
    n_sub_coalitions: int,
    n_members: int,
) -> float:
    """Compute composite topology risk score in [0, 1].

    High risk indicators:
    - Very high edge density (mesh) combined with high clustering
    - Star topology (central point of control)
    - Sub-coalitions forming
    - High degree skew (power imbalance)
    """
    risk = 0.0

    # Edge density contribution (very high or very low is suspicious)
    if edge_density > 0.85:
        risk += 0.25  # Overly connected
    elif edge_density < 0.15 and n_members > 2:
        risk += 0.15  # Suspiciously sparse

    # Degree skew (power imbalance)
    risk += degree_skew * 0.25

    # Topology-specific risk
    topology_risk = {
        "star": 0.35,
        "hierarchical": 0.15,
        "mesh": 0.10,
        "ring": 0.05,
        "unclassified": 0.10,
        "degenerate": 0.0,
    }
    risk += topology_risk.get(topology_type, 0.10)

    # Sub-coalition risk
    if n_sub_coalitions > 1:
        risk += min(0.3, n_sub_coalitions * 0.15)

    # Clustering anomaly
    if clustering > 0.8 and n_members > 3:
        risk += 0.15

    return max(0.0, min(1.0, risk))
