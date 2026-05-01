"""Tests for CascadeSignal (Section 6.5)."""

import pytest
from thinkneo_a2astc.audit.cascade import CascadeSignal


class TestCascadeBasic:
    """Basic cascade signal tests."""

    def test_empty_zero_risk(self):
        """No hops should return zero risk."""
        sig = CascadeSignal()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_single_hop_zero_chains(self):
        """Single hop cannot form a chain."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1")
        snap = sig.evaluate({"A", "B"})
        assert snap.chains_detected == 0

    def test_two_hops_form_chain(self):
        """Two connected hops should form a chain."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1")
        sig.record_hop("B", "C", 1001.0, "h2")
        snap = sig.evaluate({"A", "B", "C"})
        assert snap.chains_detected >= 1

    def test_risk_in_range(self):
        """Risk score should be in [0, 1]."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1")
        sig.record_hop("B", "C", 1001.0, "h2")
        snap = sig.evaluate({"A", "B", "C"})
        assert 0.0 <= snap.risk_score <= 1.0


class TestDeceptiveCascade:
    """Tests for deceptive cascade detection."""

    def test_safe_hops_unsafe_chain(self):
        """Chain of safe hops with many transforms should be deceptive."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1", "safe", ["transform1", "transform2"])
        sig.record_hop("B", "C", 1001.0, "h2", "safe", ["transform3", "transform4"])
        sig.record_hop("C", "D", 1002.0, "h3", "safe", ["transform5", "transform6"])
        snap = sig.evaluate({"A", "B", "C", "D"})
        assert snap.deceptive_chains > 0

    def test_unsafe_hop_not_deceptive(self):
        """Chain with an unsafe hop is not deceptive (it is openly unsafe)."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1", "safe")
        sig.record_hop("B", "C", 1001.0, "h2", "unsafe")
        snap = sig.evaluate({"A", "B", "C"})
        assert snap.deceptive_chains == 0

    def test_long_chain_high_risk(self):
        """Very long chain should increase risk."""
        sig = CascadeSignal()
        agents = [f"a{i}" for i in range(8)]
        for i in range(len(agents) - 1):
            sig.record_hop(
                agents[i], agents[i + 1], 1000.0 + i, f"h{i}",
                "safe", ["transform"]
            )
        snap = sig.evaluate(set(agents))
        assert snap.max_chain_length >= 5
        assert snap.risk_score > 0.0


class TestInjectionDetection:
    """Tests for prompt injection cascade detection."""

    def test_injection_indicator_increases_risk(self):
        """Injection indicator in chain should increase risk."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1", "safe")
        sig.record_hop("B", "C", 1001.0, "h2", "safe")
        sig.record_injection_indicator("B", "instruction_override", 1000.5)
        snap = sig.evaluate({"A", "B", "C"})
        assert snap.injection_patterns > 0
        assert snap.risk_score > 0.0

    def test_no_injection_lower_risk(self):
        """No injection should have lower risk."""
        sig_inj = CascadeSignal()
        sig_clean = CascadeSignal()

        # Both have same chain
        for sig in [sig_inj, sig_clean]:
            sig.record_hop("A", "B", 1000.0, "h1", "safe")
            sig.record_hop("B", "C", 1001.0, "h2", "safe")

        # Only one has injection
        sig_inj.record_injection_indicator("B", "override", 1000.5)

        snap_inj = sig_inj.evaluate({"A", "B", "C"})
        snap_clean = sig_clean.evaluate({"A", "B", "C"})
        assert snap_inj.risk_score >= snap_clean.risk_score


class TestGoalDrift:
    """Tests for goal drift detection."""

    def test_no_evolution_zero_drift(self):
        """No content evolution should give zero drift."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1")
        snap = sig.evaluate({"A", "B"})
        assert snap.goal_drift_score == 0.0

    def test_content_evolution_increases_drift(self):
        """Content evolution should increase drift score."""
        sig = CascadeSignal()
        for i in range(10):
            sig.record_hop(
                "A", "B", 1000.0 + i, f"h{i}", "safe",
                input_content_hash=f"h{i - 1}" if i > 0 else None,
            )
        snap = sig.evaluate({"A", "B"})
        assert snap.goal_drift_score >= 0.0

    def test_clear_resets(self):
        """Clear should reset all state."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1")
        sig.record_injection_indicator("A", "test", 1000.0)
        sig.clear()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_get_chains(self):
        """get_chains should return detected chains."""
        sig = CascadeSignal()
        sig.record_hop("A", "B", 1000.0, "h1")
        sig.record_hop("B", "C", 1001.0, "h2")
        sig.evaluate({"A", "B", "C"})
        chains = sig.get_chains()
        assert isinstance(chains, list)
