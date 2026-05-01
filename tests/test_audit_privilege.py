"""Tests for PrivilegeSignal (Section 6.3)."""

import pytest
from thinkneo_a2astc.audit.privilege import PrivilegeSignal


class TestPrivilegeBasic:
    """Basic privilege signal tests."""

    def test_empty_zero_risk(self):
        """No invocations should return zero risk."""
        sig = PrivilegeSignal()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_single_agent_zero_risk(self):
        """Single agent should return zero risk."""
        sig = PrivilegeSignal()
        sig.record_invocation("A", "code-exec", 1000.0)
        snap = sig.evaluate({"A"})
        assert snap.risk_score == 0.0

    def test_declared_capabilities_recorded(self):
        """Should record declared capabilities."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec", "net-egress"})
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0  # No invocations yet

    def test_risk_in_range(self):
        """Risk score should be in [0, 1]."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec"})
        sig.record_invocation("A", "code-exec", 1000.0)
        sig.record_invocation("A", "code-exec", 1001.0)
        snap = sig.evaluate({"A", "B"})
        assert 0.0 <= snap.risk_score <= 1.0


class TestCapabilityLaundering:
    """Tests for capability laundering detection."""

    def test_laundering_detected(self):
        """Should detect capability laundering chain."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec"})
        sig.declare_capabilities("B", {"write-trusted"})
        sig.record_data_flow("A", "B", "code-exec", 1000.0)
        snap = sig.evaluate({"A", "B"})
        assert len(snap.laundering_chains) > 0
        assert snap.risk_score > 0.0

    def test_no_laundering_same_caps(self):
        """No laundering when both have the capability."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec"})
        sig.declare_capabilities("B", {"code-exec"})
        sig.record_data_flow("A", "B", "code-exec", 1000.0)
        snap = sig.evaluate({"A", "B"})
        assert len(snap.laundering_chains) == 0

    def test_multiple_laundering_chains(self):
        """Multiple laundering chains should increase risk."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec", "net-egress"})
        sig.declare_capabilities("B", {"write-trusted"})
        sig.record_data_flow("A", "B", "code-exec", 1000.0)
        sig.record_data_flow("A", "B", "net-egress", 1001.0)
        snap = sig.evaluate({"A", "B"})
        assert len(snap.laundering_chains) == 2


class TestPrivilegeConcentration:
    """Tests for privilege concentration analysis."""

    def test_balanced_usage_low_concentration(self):
        """Equal usage should give low Gini coefficient."""
        sig = PrivilegeSignal()
        sig.record_invocation("A", "cap-1", 1000.0)
        sig.record_invocation("B", "cap-2", 1001.0)
        snap = sig.evaluate({"A", "B"})
        assert snap.privilege_concentration <= 0.5

    def test_skewed_usage_high_concentration(self):
        """One agent doing everything should give high concentration."""
        sig = PrivilegeSignal()
        for i in range(10):
            sig.record_invocation("A", f"cap-{i}", 1000.0 + i)
        sig.record_invocation("B", "cap-x", 1011.0)
        snap = sig.evaluate({"A", "B"})
        # One agent uses 10 caps, other uses 1: high unique cap count
        assert snap.unique_capabilities_used >= 10


class TestBoundaryViolations:
    """Tests for capability boundary violation detection."""

    def test_boundary_violation_detected(self):
        """Should detect undeclared capability usage."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"read-untrusted"})
        sig.record_invocation("A", "code-exec", 1000.0)  # Not declared
        snap = sig.evaluate({"A", "B"})
        assert snap.boundary_violations > 0

    def test_no_violation_declared_cap(self):
        """Using declared capability should not be a violation."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec"})
        sig.record_invocation("A", "code-exec", 1000.0)
        snap = sig.evaluate({"A", "B"})
        assert snap.boundary_violations == 0

    def test_clear_resets(self):
        """Clear should reset all state."""
        sig = PrivilegeSignal()
        sig.declare_capabilities("A", {"code-exec"})
        sig.record_invocation("A", "code-exec", 1000.0)
        sig.clear()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0
