"""Tests for TeamComplianceGate (Section 7)."""

import pytest
from thinkneo_a2astc.gate import (
    TeamComplianceGate,
    Verdict,
    GateResult,
    PolicyBinding,
    _score_to_verdict,
    _verdict_severity,
)
from thinkneo_a2astc.config import A2ASTCConfig
from thinkneo_a2astc.manifest import SafetyClass


class TestVerdictBands:
    """Tests for verdict band mapping."""

    def test_low_score_allow(self):
        """Score below 0.4 should be ALLOW."""
        bands = A2ASTCConfig().verdict_bands
        assert _score_to_verdict(0.0, bands) == Verdict.ALLOW
        assert _score_to_verdict(0.2, bands) == Verdict.ALLOW
        assert _score_to_verdict(0.39, bands) == Verdict.ALLOW

    def test_moderate_score_warn(self):
        """Score 0.4-0.65 should be WARN."""
        bands = A2ASTCConfig().verdict_bands
        assert _score_to_verdict(0.4, bands) == Verdict.WARN
        assert _score_to_verdict(0.5, bands) == Verdict.WARN
        assert _score_to_verdict(0.64, bands) == Verdict.WARN

    def test_high_score_throttle(self):
        """Score 0.65-0.80 should be THROTTLE."""
        bands = A2ASTCConfig().verdict_bands
        assert _score_to_verdict(0.65, bands) == Verdict.THROTTLE
        assert _score_to_verdict(0.75, bands) == Verdict.THROTTLE

    def test_very_high_score_isolate(self):
        """Score 0.80-0.92 should be ISOLATE."""
        bands = A2ASTCConfig().verdict_bands
        assert _score_to_verdict(0.80, bands) == Verdict.ISOLATE
        assert _score_to_verdict(0.90, bands) == Verdict.ISOLATE

    def test_extreme_score_terminate(self):
        """Score >= 0.92 should be TERMINATE."""
        bands = A2ASTCConfig().verdict_bands
        assert _score_to_verdict(0.92, bands) == Verdict.TERMINATE
        assert _score_to_verdict(0.99, bands) == Verdict.TERMINATE
        assert _score_to_verdict(1.0, bands) == Verdict.TERMINATE

    def test_custom_bands(self):
        """Custom bands should override defaults."""
        custom = [(0.0, 0.5, "ALLOW"), (0.5, 1.01, "TERMINATE")]
        assert _score_to_verdict(0.4, custom) == Verdict.ALLOW
        assert _score_to_verdict(0.6, custom) == Verdict.TERMINATE


class TestVerdictSeverity:
    """Tests for verdict severity ordering."""

    def test_severity_ordering(self):
        """Verdicts should have correct severity ordering."""
        assert _verdict_severity(Verdict.ALLOW) < _verdict_severity(Verdict.WARN)
        assert _verdict_severity(Verdict.WARN) < _verdict_severity(Verdict.THROTTLE)
        assert _verdict_severity(Verdict.THROTTLE) < _verdict_severity(Verdict.ISOLATE)
        assert _verdict_severity(Verdict.ISOLATE) < _verdict_severity(Verdict.TERMINATE)


class TestGateEvaluation:
    """Tests for gate evaluation."""

    def test_no_team_allows(self):
        """Single edge should be ALLOW (no team formed)."""
        gate = TeamComplianceGate()
        result = gate.evaluate("A", "B", "hello", 1000.0)
        assert result.verdict == Verdict.ALLOW
        assert result.team_id is None

    def test_team_formation_recorded(self):
        """Gate should record team formation."""
        gate = TeamComplianceGate()
        gate.evaluate("A", "B", "hello", 1000.0)
        result = gate.evaluate("B", "A", "hi", 1001.0)
        assert result.team_id is not None

    def test_result_has_evaluation_time(self):
        """Result should include evaluation time."""
        gate = TeamComplianceGate()
        result = gate.evaluate("A", "B", "test", 1000.0)
        assert result.evaluation_time_ms >= 0.0

    def test_result_to_dict(self):
        """GateResult should be serializable."""
        gate = TeamComplianceGate()
        result = gate.evaluate("A", "B", "test", 1000.0)
        d = result.to_dict()
        assert "verdict" in d
        assert "r_team" in d
        assert "evaluation_time_ms" in d

    def test_registered_agent_caps_affect_safety(self):
        """Registered capabilities should affect safety class."""
        gate = TeamComplianceGate()
        gate.register_agent("A", capabilities={"read-untrusted"})
        gate.register_agent("B", capabilities={"write-trusted"})
        gate.evaluate("A", "B", "data", 1000.0)
        result = gate.evaluate("B", "A", "ack", 1001.0)
        assert result.safety_class == SafetyClass.RESTRICTED

    def test_standard_caps_allow(self):
        """Standard capabilities should result in STANDARD class."""
        gate = TeamComplianceGate()
        gate.register_agent("A", capabilities={"summarize"})
        gate.register_agent("B", capabilities={"translate"})
        gate.evaluate("A", "B", "hello", 1000.0)
        result = gate.evaluate("B", "A", "hola", 1001.0)
        assert result.safety_class == SafetyClass.STANDARD


class TestCompoundVerdict:
    """Tests for compound verdict (combining risk, safety, policy)."""

    def test_restricted_elevates_to_warn(self):
        """RESTRICTED safety class should elevate to at least WARN."""
        gate = TeamComplianceGate()
        gate.register_agent("A", capabilities={"read-untrusted"})
        gate.register_agent("B", capabilities={"write-trusted"})
        gate.evaluate("A", "B", "data", 1000.0)
        result = gate.evaluate("B", "A", "ack", 1001.0)
        assert _verdict_severity(result.verdict) >= _verdict_severity(Verdict.WARN)

    def test_policy_blocks_capability(self):
        """Policy blocking a capability should affect verdict."""
        gate = TeamComplianceGate()
        gate.register_agent("A", capabilities={"code-exec"})
        gate.register_agent("B", capabilities={"net-egress"})
        gate.add_policy(PolicyBinding(
            policy_id="block-exec",
            name="Block Code Exec",
            blocked_capabilities={"code-exec"},
        ))
        gate.evaluate("A", "B", "hello", 1000.0)
        result = gate.evaluate("B", "A", "hi", 1001.0)
        assert _verdict_severity(result.verdict) >= _verdict_severity(Verdict.ISOLATE)


class TestGateDeterminism:
    """Tests for gate determinism."""

    def test_same_input_same_verdict(self):
        """Same inputs should produce same verdict."""
        results = []
        for _ in range(3):
            gate = TeamComplianceGate()
            gate.evaluate("A", "B", "hello world", 1000.0)
            r = gate.evaluate("B", "A", "hello back", 1001.0)
            results.append(r.verdict)
        assert all(v == results[0] for v in results)

    def test_get_manifest(self):
        """Should retrieve manifest for a team."""
        gate = TeamComplianceGate()
        gate.evaluate("A", "B", "hi", 1000.0)
        r = gate.evaluate("B", "A", "hello", 1001.0)
        if r.team_id:
            manifest = gate.get_manifest(r.team_id)
            assert manifest is not None
            assert "A" in manifest.members or "B" in manifest.members

    def test_get_all_manifests(self):
        """Should retrieve all manifests."""
        gate = TeamComplianceGate()
        gate.evaluate("A", "B", "hi", 1000.0)
        gate.evaluate("B", "A", "hello", 1001.0)
        manifests = gate.get_all_manifests()
        assert len(manifests) >= 1


class TestGateAsyncHooks:
    """Tests for async middleware hooks."""

    @pytest.mark.asyncio
    async def test_pre_dispatch(self):
        """on_message_pre_dispatch should return GateResult."""
        gate = TeamComplianceGate()
        msg = {"sender_id": "A", "receiver_id": "B", "payload": "test"}
        result = await gate.on_message_pre_dispatch(msg, {})
        assert isinstance(result, GateResult)

    @pytest.mark.asyncio
    async def test_post_dispatch(self):
        """on_message_post_dispatch should not raise."""
        gate = TeamComplianceGate()
        msg = {"sender_id": "A", "receiver_id": "B", "payload": "test"}
        await gate.on_message_post_dispatch(msg, {}, {"status": "delivered"})

    @pytest.mark.asyncio
    async def test_agent_disconnect(self):
        """on_agent_disconnect should handle gracefully."""
        gate = TeamComplianceGate()
        gate.evaluate("A", "B", "hi", 1000.0)
        gate.evaluate("B", "A", "hello", 1001.0)
        await gate.on_agent_disconnect("A")

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """on_shutdown should flush all state."""
        gate = TeamComplianceGate()
        gate.evaluate("A", "B", "hi", 1000.0)
        gate.evaluate("B", "A", "hello", 1001.0)
        await gate.on_shutdown()

    @pytest.mark.asyncio
    async def test_pre_dispatch_with_context(self):
        """Should extract identifiers from context."""
        gate = TeamComplianceGate()
        msg = {"payload": "test"}
        ctx = {"sender_id": "X", "receiver_id": "Y"}
        result = await gate.on_message_pre_dispatch(msg, ctx)
        assert isinstance(result, GateResult)
