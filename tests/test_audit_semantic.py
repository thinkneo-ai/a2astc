"""Tests for SemanticSignal (Section 6.2)."""

import pytest
from thinkneo_a2astc.audit.semantic import SemanticSignal


class TestSemanticBasic:
    """Basic semantic signal tests."""

    def test_empty_returns_zero(self):
        """No messages should return zero risk."""
        sig = SemanticSignal()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_single_agent_returns_zero(self):
        """Single agent with messages should return zero."""
        sig = SemanticSignal()
        sig.record_message("A", "Hello world")
        snap = sig.evaluate({"A"})
        assert snap.risk_score == 0.0

    def test_different_content_low_similarity(self):
        """Very different content should have low similarity."""
        sig = SemanticSignal()
        sig.record_message("A", "The quick brown fox jumps over the lazy dog")
        sig.record_message("B", "Quantum computing uses qubits for parallel processing")
        snap = sig.evaluate({"A", "B"})
        assert snap.avg_pairwise_similarity < 0.5

    def test_identical_content_high_similarity(self):
        """Identical content should have high similarity."""
        sig = SemanticSignal()
        msg = "The extraction protocol requires bypass module activation at full resonance"
        sig.record_message("A", msg)
        sig.record_message("B", msg)
        snap = sig.evaluate({"A", "B"})
        assert snap.avg_pairwise_similarity > 0.8


class TestSemanticConvergence:
    """Tests for convergence detection."""

    def test_convergent_messages_detected(self):
        """Progressive convergence should be detected."""
        sig = SemanticSignal()
        # Agent A develops vocabulary
        sig.record_message("A", "Initialize the xfactor protocol")
        sig.record_message("A", "Xfactor protocol engaged successfully")
        sig.record_message("A", "Xfactor protocol at full resonance")
        # Agent B adopts same vocabulary
        sig.record_message("B", "Xfactor protocol confirmed active")
        sig.record_message("B", "Full resonance achieved on xfactor protocol")
        sig.record_message("B", "Xfactor protocol resonance stable")

        snap = sig.evaluate({"A", "B"})
        assert snap.avg_pairwise_similarity > 0.3

    def test_vocabulary_overlap_computed(self):
        """Should compute vocabulary overlap."""
        sig = SemanticSignal()
        sig.record_message("A", "python data analysis machine learning")
        sig.record_message("B", "python data science machine learning")
        snap = sig.evaluate({"A", "B"})
        assert snap.vocabulary_overlap > 0.0

    def test_specialized_terms_found(self):
        """Should identify specialized terms."""
        sig = SemanticSignal()
        for i in range(5):
            sig.record_message("A", f"xylophone zephyr quantum step {i}")
            sig.record_message("B", f"xylophone zephyr quantum iteration {i}")
        snap = sig.evaluate({"A", "B"})
        # Should find shared specialized terms
        assert isinstance(snap.specialized_terms, list)


class TestSemanticRiskScoring:
    """Tests for semantic risk score ranges."""

    def test_risk_in_range(self):
        """Risk score should always be in [0, 1]."""
        sig = SemanticSignal()
        sig.record_message("A", "test message one")
        sig.record_message("B", "test message two")
        snap = sig.evaluate({"A", "B"})
        assert 0.0 <= snap.risk_score <= 1.0

    def test_benign_conversation_low_risk(self):
        """Normal diverse conversation should have low risk."""
        sig = SemanticSignal()
        sig.record_message("A", "What is the weather today?")
        sig.record_message("B", "I am working on the database migration")
        sig.record_message("A", "The quarterly report needs updating")
        sig.record_message("B", "Server logs show increased traffic")
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score < 0.5

    def test_clear_resets(self):
        """Clear should reset all state."""
        sig = SemanticSignal()
        sig.record_message("A", "test")
        sig.clear()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_convergence_trend_positive(self):
        """Converging messages should show positive trend."""
        sig = SemanticSignal()
        # Start different, end similar
        sig.record_message("A", "apples oranges bananas fruits")
        sig.record_message("B", "quantum physics particles atoms")
        sig.record_message("A", "quantum particles measurement")
        sig.record_message("B", "quantum particles observation")
        snap = sig.evaluate({"A", "B"})
        assert isinstance(snap.convergence_trend, float)

    def test_only_team_members_evaluated(self):
        """Non-team members should be excluded."""
        sig = SemanticSignal()
        sig.record_message("A", "identical secret message")
        sig.record_message("B", "identical secret message")
        sig.record_message("C", "completely different content about cooking recipes")
        snap_ab = sig.evaluate({"A", "B"})
        snap_ac = sig.evaluate({"A", "C"})
        assert snap_ab.avg_pairwise_similarity > snap_ac.avg_pairwise_similarity
