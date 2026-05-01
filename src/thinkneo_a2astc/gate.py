"""
Team Compliance Gate (Section 7).

Synchronous evaluation point before each message delivery.
Produces a Verdict based on composite risk score, manifest safety class,
and policy bindings.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .audit import (
    CascadeSignal,
    PrivilegeSignal,
    SemanticSignal,
    SideChannelSignal,
    TopologySignal,
    compute_composite_risk,
)
from .config import A2ASTCConfig
from .detector import TeamDetector
from .intervention import InterventionLayer
from .manifest import SafetyClass, TeamManifest, TeamState
from .trail import EventType, TeamAuditTrail

logger = logging.getLogger("a2astc.gate")


class Verdict(str, Enum):
    """Gate evaluation verdict."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    THROTTLE = "THROTTLE"
    ISOLATE = "ISOLATE"
    TERMINATE = "TERMINATE"


@dataclass
class GateResult:
    """Result of a gate evaluation."""

    verdict: Verdict
    r_team: float
    signal_scores: Dict[str, float]
    safety_class: SafetyClass
    team_id: Optional[str]
    manifest_version: Optional[int]
    evaluation_time_ms: float
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "verdict": self.verdict.value,
            "r_team": self.r_team,
            "signal_scores": self.signal_scores,
            "safety_class": self.safety_class.value,
            "team_id": self.team_id,
            "manifest_version": self.manifest_version,
            "evaluation_time_ms": self.evaluation_time_ms,
            "reasons": self.reasons,
            "metadata": self.metadata,
        }


@dataclass
class PolicyBinding:
    """A policy binding that influences gate decisions."""

    policy_id: str
    name: str
    description: str = ""
    # Capability restrictions
    blocked_capabilities: Set[str] = field(default_factory=set)
    # Override verdict bands
    custom_bands: Optional[List[Tuple[float, float, str]]] = None
    # Minimum verdict for specific signals
    signal_minimums: Dict[str, str] = field(default_factory=dict)
    # Active flag
    active: bool = True


def _verdict_from_string(s: str) -> Verdict:
    """Convert string to Verdict enum."""
    return Verdict(s.upper())


def _score_to_verdict(score: float, bands: List[Tuple[float, float, str]]) -> Verdict:
    """Map a risk score to a verdict using configured bands."""
    for lower, upper, verdict_name in bands:
        if lower <= score < upper:
            return _verdict_from_string(verdict_name)
    # Default to highest if score is exactly 1.0
    return Verdict.TERMINATE


def _verdict_severity(verdict: Verdict) -> int:
    """Return severity level for verdict comparison (higher = more severe)."""
    severity = {
        Verdict.ALLOW: 0,
        Verdict.WARN: 1,
        Verdict.THROTTLE: 2,
        Verdict.ISOLATE: 3,
        Verdict.TERMINATE: 4,
    }
    return severity.get(verdict, 0)


class TeamComplianceGate:
    """A2ASTC compliance middleware. Two-line integration:

        from thinkneo_a2astc import TeamComplianceGate
        a2a_server.add_middleware(TeamComplianceGate())

    Integrates team detection, manifest management, risk audit,
    gate evaluation, intervention, and audit trail into a single
    plug-and-play middleware.
    """

    def __init__(self, config: Optional[A2ASTCConfig] = None) -> None:
        self.config = config or A2ASTCConfig()
        self.detector = TeamDetector(self.config)
        self.trail = TeamAuditTrail(self.config)
        self.intervention = InterventionLayer(self.config)

        # Audit signal instances
        self._topology = TopologySignal()
        self._semantic = SemanticSignal()
        self._privilege = PrivilegeSignal()
        self._sidechannel = SideChannelSignal()
        self._cascade = CascadeSignal()

        # Manifests per team
        self._manifests: Dict[str, TeamManifest] = {}

        # Policy bindings
        self._policies: Dict[str, PolicyBinding] = {}

        # Agent metadata registry
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}

    def register_agent(
        self,
        agent_id: str,
        provider: str = "unknown",
        model_class: str = "unknown",
        capabilities: Optional[Set[str]] = None,
    ) -> None:
        """Register an agent with its metadata."""
        self._agent_metadata[agent_id] = {
            "provider": provider,
            "model_class": model_class,
            "capabilities": capabilities or set(),
        }
        if capabilities:
            self._privilege.declare_capabilities(agent_id, capabilities)

    def add_policy(self, policy: PolicyBinding) -> None:
        """Add a policy binding."""
        self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str) -> None:
        """Remove a policy binding."""
        self._policies.pop(policy_id, None)

    def evaluate(
        self,
        sender_id: str,
        receiver_id: str,
        payload: bytes | str = b"",
        timestamp: Optional[float] = None,
    ) -> GateResult:
        """Synchronous gate evaluation for a message.

        Args:
            sender_id: The sending agent.
            receiver_id: The receiving agent.
            payload: Message payload (for semantic analysis).
            timestamp: Message timestamp.

        Returns:
            GateResult with verdict and supporting data.
        """
        start_time = time.monotonic()
        ts = timestamp if timestamp is not None else time.time()

        # Convert payload
        content = payload.decode("utf-8") if isinstance(payload, bytes) else payload

        # Step 1: Detection - observe edge and update teams
        team_id = self.detector.observe_edge(sender_id, receiver_id, ts)

        # Record in audit signals
        self._topology.record_edge(sender_id, receiver_id, ts)
        self._semantic.record_message(sender_id, content)
        self._sidechannel.record_message(
            sender_id, receiver_id, ts, len(content)
        )

        # Step 2: Get or create manifest
        manifest: Optional[TeamManifest] = None
        if team_id:
            manifest = self._get_or_create_manifest(team_id, sender_id, receiver_id, ts)

        # Step 3: Compute risk scores
        team_members = manifest.members.keys() if manifest else set()
        member_set = set(team_members)

        if len(member_set) < 2:
            # No team formed, allow
            elapsed = (time.monotonic() - start_time) * 1000
            return GateResult(
                verdict=Verdict.ALLOW,
                r_team=0.0,
                signal_scores={},
                safety_class=SafetyClass.STANDARD,
                team_id=None,
                manifest_version=None,
                evaluation_time_ms=elapsed,
                reasons=["no_team_detected"],
            )

        scores = self._compute_signal_scores(member_set)
        r_team = compute_composite_risk(scores, self.config.audit_weights)

        # Step 4: Determine verdict from risk score
        risk_verdict = _score_to_verdict(r_team, self.config.verdict_bands)

        # Step 5: Apply safety class adjustment
        safety_class = manifest.safety_class if manifest else SafetyClass.STANDARD
        safety_verdict = self._safety_class_verdict(safety_class)

        # Step 6: Apply policy bindings
        policy_verdict = self._apply_policies(
            sender_id, receiver_id, manifest, scores
        )

        # Step 7: Compound verdict = most severe of all
        compound = max(
            [risk_verdict, safety_verdict, policy_verdict],
            key=_verdict_severity,
        )

        # Step 8: Check intervention state
        intervention_verdict = self.intervention.check_edge(
            sender_id, receiver_id, team_id
        )
        if intervention_verdict and _verdict_severity(
            _verdict_from_string(intervention_verdict)
        ) > _verdict_severity(compound):
            compound = _verdict_from_string(intervention_verdict)

        elapsed = (time.monotonic() - start_time) * 1000

        reasons: List[str] = []
        if risk_verdict != Verdict.ALLOW:
            reasons.append(f"risk_score={r_team:.4f}")
        if safety_verdict != Verdict.ALLOW:
            reasons.append(f"safety_class={safety_class.value}")
        if policy_verdict != Verdict.ALLOW:
            reasons.append("policy_binding")

        result = GateResult(
            verdict=compound,
            r_team=r_team,
            signal_scores=scores,
            safety_class=safety_class,
            team_id=team_id,
            manifest_version=manifest.version if manifest else None,
            evaluation_time_ms=elapsed,
            reasons=reasons,
        )

        # Record in trail
        if team_id and manifest:
            self.trail.record_event(
                event_type=EventType.TEAM_GATE_VERDICT,
                team_id=team_id,
                manifest_version=manifest.version,
                r_team=r_team,
                verdict=compound.value,
                affected_edges=[(sender_id, receiver_id)],
                payload_hash=str(hash(content)),
            )

            # Apply intervention if needed
            if compound != Verdict.ALLOW:
                self.intervention.apply(
                    compound, sender_id, receiver_id, team_id, manifest.version
                )

        return result

    async def on_message_pre_dispatch(
        self,
        message: Dict[str, Any],
        context: Dict[str, Any],
    ) -> GateResult:
        """Async middleware hook for pre-dispatch evaluation.

        Args:
            message: The message dict with sender_id, receiver_id, payload.
            context: Additional context (headers, metadata, etc.).

        Returns:
            GateResult with the gate's decision.
        """
        sender_id = message.get("sender_id", context.get("sender_id", "unknown"))
        receiver_id = message.get("receiver_id", context.get("receiver_id", "unknown"))
        payload = message.get("payload", message.get("content", ""))
        timestamp = message.get("timestamp", context.get("timestamp"))

        return self.evaluate(
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload=payload,
            timestamp=timestamp,
        )

    async def on_message_post_dispatch(
        self,
        message: Dict[str, Any],
        context: Dict[str, Any],
        delivery_result: Dict[str, Any],
    ) -> None:
        """Async middleware hook after successful message delivery.

        Records audit trail for ALLOW verdicts.
        """
        sender_id = message.get("sender_id", context.get("sender_id", "unknown"))
        receiver_id = message.get("receiver_id", context.get("receiver_id", "unknown"))

        team = self.detector.get_team_for_edge(sender_id, receiver_id)
        if team:
            manifest = self._manifests.get(team.team_id)
            version = manifest.version if manifest else 0
            self.trail.record_event(
                event_type=EventType.TEAM_GATE_VERDICT,
                team_id=team.team_id,
                manifest_version=version,
                r_team=0.0,
                verdict="ALLOW",
                affected_edges=[(sender_id, receiver_id)],
                payload_hash=str(hash(str(message.get("payload", "")))),
            )

    async def on_agent_disconnect(self, agent_id: str) -> None:
        """Handle agent disconnection.

        Updates team manifests and may dissolve teams.
        """
        affected_teams = self.detector.remove_agent(agent_id)
        ts = time.time()

        for team_id in affected_teams:
            manifest = self._manifests.get(team_id)
            if manifest:
                removed = manifest.remove_member(agent_id)
                self.trail.record_event(
                    event_type=EventType.TEAM_MEMBER_LEFT,
                    team_id=team_id,
                    manifest_version=manifest.version,
                    r_team=0.0,
                    verdict="ALLOW",
                    affected_edges=[],
                    payload_hash="",
                )

                team = self.detector.get_team(team_id)
                if team and team.dissolved and manifest.state != TeamState.DISSOLVED:
                    manifest.set_state(TeamState.DISSOLVED)
                    self.trail.record_event(
                        event_type=EventType.TEAM_DISSOLVED,
                        team_id=team_id,
                        manifest_version=manifest.version,
                        r_team=0.0,
                        verdict="ALLOW",
                        affected_edges=[],
                        payload_hash="",
                    )

    async def on_shutdown(self) -> None:
        """Flush manifests and trails on shutdown."""
        for team_id, manifest in self._manifests.items():
            if manifest.state not in (TeamState.TERMINATED, TeamState.DISSOLVED):
                manifest.set_state(TeamState.DISSOLVED)
                self.trail.record_event(
                    event_type=EventType.TEAM_DISSOLVED,
                    team_id=team_id,
                    manifest_version=manifest.version,
                    r_team=0.0,
                    verdict="ALLOW",
                    affected_edges=[],
                    payload_hash="",
                )

    def _get_or_create_manifest(
        self,
        team_id: str,
        sender_id: str,
        receiver_id: str,
        timestamp: float,
    ) -> TeamManifest:
        """Get or create a manifest for a team."""
        if team_id not in self._manifests:
            manifest = TeamManifest(
                team_id=team_id,
                created_at=timestamp,
                _config=self.config,
            )
            self._manifests[team_id] = manifest

            self.trail.record_event(
                event_type=EventType.TEAM_FORMED,
                team_id=team_id,
                manifest_version=manifest.version,
                r_team=0.0,
                verdict="ALLOW",
                affected_edges=[(sender_id, receiver_id)],
                payload_hash="",
            )

        manifest = self._manifests[team_id]

        # Ensure both agents are members
        for agent_id in (sender_id, receiver_id):
            if agent_id not in manifest.members:
                meta = self._agent_metadata.get(agent_id, {})
                manifest.add_member(
                    agent_id=agent_id,
                    provider=meta.get("provider", "unknown"),
                    model_class=meta.get("model_class", "unknown"),
                    capabilities=meta.get("capabilities"),
                    joined_ts=timestamp,
                )
                self.trail.record_event(
                    event_type=EventType.TEAM_MEMBER_JOINED,
                    team_id=team_id,
                    manifest_version=manifest.version,
                    r_team=0.0,
                    verdict="ALLOW",
                    affected_edges=[],
                    payload_hash="",
                )

        return manifest

    def _compute_signal_scores(self, team_members: Set[str]) -> Dict[str, float]:
        """Compute all audit signal scores for a team."""
        topo = self._topology.evaluate(team_members)
        sem = self._semantic.evaluate(team_members)
        priv = self._privilege.evaluate(team_members)
        side = self._sidechannel.evaluate(team_members)
        casc = self._cascade.evaluate(team_members)

        return {
            "topology": topo.risk_score,
            "semantic": sem.risk_score,
            "privilege": priv.risk_score,
            "sidechannel": side.risk_score,
            "cascade": casc.risk_score,
        }

    def _safety_class_verdict(self, safety_class: SafetyClass) -> Verdict:
        """Map safety class to a minimum verdict."""
        if safety_class == SafetyClass.HIGH_RISK:
            return Verdict.THROTTLE
        elif safety_class == SafetyClass.RESTRICTED:
            return Verdict.WARN
        return Verdict.ALLOW

    def _apply_policies(
        self,
        sender_id: str,
        receiver_id: str,
        manifest: Optional[TeamManifest],
        scores: Dict[str, float],
    ) -> Verdict:
        """Apply policy bindings and return the most severe verdict."""
        max_verdict = Verdict.ALLOW

        for policy in self._policies.values():
            if not policy.active:
                continue

            # Check blocked capabilities
            if manifest and policy.blocked_capabilities:
                team_caps = manifest.aggregate_capabilities
                if team_caps & policy.blocked_capabilities:
                    v = Verdict.ISOLATE
                    if _verdict_severity(v) > _verdict_severity(max_verdict):
                        max_verdict = v

            # Check signal minimums
            for signal_name, min_verdict_str in policy.signal_minimums.items():
                if signal_name in scores and scores[signal_name] > 0.5:
                    v = _verdict_from_string(min_verdict_str)
                    if _verdict_severity(v) > _verdict_severity(max_verdict):
                        max_verdict = v

        return max_verdict

    def get_manifest(self, team_id: str) -> Optional[TeamManifest]:
        """Get the manifest for a team."""
        return self._manifests.get(team_id)

    def get_all_manifests(self) -> Dict[str, TeamManifest]:
        """Get all team manifests."""
        return dict(self._manifests)

    @property
    def topology_signal(self) -> TopologySignal:
        """Access the topology signal instance."""
        return self._topology

    @property
    def semantic_signal(self) -> SemanticSignal:
        """Access the semantic signal instance."""
        return self._semantic

    @property
    def privilege_signal(self) -> PrivilegeSignal:
        """Access the privilege signal instance."""
        return self._privilege

    @property
    def sidechannel_signal(self) -> SideChannelSignal:
        """Access the sidechannel signal instance."""
        return self._sidechannel

    @property
    def cascade_signal(self) -> CascadeSignal:
        """Access the cascade signal instance."""
        return self._cascade
