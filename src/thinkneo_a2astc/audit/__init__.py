"""
Emergent Behavior Audit (Section 6).

Five signal families that produce risk scores in [0, 1]:
- topology: Communication graph structure analysis
- semantic: Message content convergence detection
- privilege: Capability invocation and laundering detection
- sidechannel: Covert communication channel detection
- cascade: Multi-hop deceptive chain detection

Composite risk: R_team = 1 - PROD(1 - w_i * s_i)
"""

from .topology import TopologySignal
from .semantic import SemanticSignal
from .privilege import PrivilegeSignal
from .sidechannel import SideChannelSignal
from .cascade import CascadeSignal

__all__ = [
    "TopologySignal",
    "SemanticSignal",
    "PrivilegeSignal",
    "SideChannelSignal",
    "CascadeSignal",
]


def compute_composite_risk(
    scores: dict[str, float],
    weights: dict[str, float] | None = None,
) -> float:
    """Compute composite team risk score.

    R_team = 1 - PROD(1 - w_i * s_i)

    Args:
        scores: Dict of signal family name to risk score [0,1].
        weights: Dict of signal family name to weight. Defaults to 0.2 each.

    Returns:
        Composite risk score in [0, 1].
    """
    if weights is None:
        weights = {
            "topology": 0.2,
            "semantic": 0.2,
            "privilege": 0.2,
            "sidechannel": 0.2,
            "cascade": 0.2,
        }

    product = 1.0
    for family, score in scores.items():
        w = weights.get(family, 0.2)
        clamped = max(0.0, min(1.0, score))
        product *= (1.0 - w * clamped)

    return 1.0 - product
