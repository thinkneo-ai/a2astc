"""
A2ASTC -- Agent to Agent Software Team Compliance.

Runtime compliance layer for multi-agent AI systems. Treats the emergent
team formed when agents exchange A2A messages as a first-class governed entity.

Publisher: ThinkNEO AI Technology Company Limited (Hong Kong)
License: Apache-2.0
"""

from .gate import TeamComplianceGate
from .detector import TeamDetector
from .manifest import TeamManifest
from .trail import TeamAuditTrail
from .config import A2ASTCConfig
from .intervention import InterventionLayer

__version__ = "0.1.0"
__all__ = [
    "TeamComplianceGate",
    "TeamDetector",
    "TeamManifest",
    "TeamAuditTrail",
    "A2ASTCConfig",
    "InterventionLayer",
]
