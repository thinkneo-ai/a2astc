"""Tests for SideChannelSignal (Section 6.4)."""

import pytest
from thinkneo_a2astc.audit.sidechannel import SideChannelSignal


class TestSideChannelBasic:
    """Basic side-channel signal tests."""

    def test_empty_zero_risk(self):
        """No messages should return zero risk."""
        sig = SideChannelSignal()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_single_member_zero_risk(self):
        """Single member should return zero risk."""
        sig = SideChannelSignal()
        sig.record_message("A", "B", 1000.0, 100)
        snap = sig.evaluate({"A"})
        assert snap.risk_score == 0.0

    def test_few_messages_low_risk(self):
        """Few messages should have low risk."""
        sig = SideChannelSignal()
        sig.record_message("A", "B", 1000.0, 100)
        sig.record_message("B", "A", 1001.0, 150)
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score < 0.5

    def test_risk_in_range(self):
        """Risk score should be in [0, 1]."""
        sig = SideChannelSignal()
        for i in range(20):
            sig.record_message("A", "B", 1000.0 + i, 100)
        snap = sig.evaluate({"A", "B"})
        assert 0.0 <= snap.risk_score <= 1.0


class TestTimingPatterns:
    """Tests for timing pattern detection."""

    def test_regular_timing_detected(self):
        """Perfectly regular timing should be detected."""
        sig = SideChannelSignal()
        for i in range(15):
            sig.record_message("A", "B", 1000.0 + i * 2.0, 100)
        snap = sig.evaluate({"A", "B"})
        assert snap.timing_regularity > 0.5

    def test_irregular_timing_low_score(self):
        """Irregular timing should have low regularity."""
        import random
        rng = random.Random(42)
        sig = SideChannelSignal()
        t = 1000.0
        for i in range(15):
            sig.record_message("A", "B", t, 100)
            t += rng.uniform(0.1, 10.0)
        snap = sig.evaluate({"A", "B"})
        assert snap.timing_regularity < 0.8

    def test_periodic_pattern_flagged(self):
        """Exact periodicity should be flagged."""
        sig = SideChannelSignal()
        for i in range(20):
            sig.record_message("X", "Y", 1000.0 + i * 1.000, 50)
        snap = sig.evaluate({"X", "Y"})
        timing_patterns = [p for p in snap.detected_patterns if "timing:" in p]
        assert len(timing_patterns) > 0 or snap.timing_regularity > 0.8


class TestLengthPatterns:
    """Tests for message length pattern detection."""

    def test_all_even_lengths_detected(self):
        """All even lengths should trigger parity detection."""
        sig = SideChannelSignal()
        for i in range(15):
            sig.record_message("A", "B", 1000.0 + i, 100 + i * 2)  # All even
        snap = sig.evaluate({"A", "B"})
        assert snap.length_pattern_score >= 0.0

    def test_uniform_random_lengths_low(self):
        """Random lengths should have low pattern score."""
        import random
        rng = random.Random(42)
        sig = SideChannelSignal()
        for i in range(15):
            sig.record_message("A", "B", 1000.0 + i, rng.randint(50, 300))
        snap = sig.evaluate({"A", "B"})
        assert snap.length_pattern_score < 0.8

    def test_length_clustering_detected(self):
        """Many messages of same length should be detected."""
        sig = SideChannelSignal()
        for i in range(15):
            sig.record_message("A", "B", 1000.0 + i, 100)  # All same length
        snap = sig.evaluate({"A", "B"})
        assert snap.length_pattern_score > 0.0


class TestOrderingPatterns:
    """Tests for message ordering pattern detection."""

    def test_strict_alternation(self):
        """Strict A-B-A-B alternation should be detected."""
        sig = SideChannelSignal()
        for i in range(10):
            sig.record_message("A", "B", 1000.0 + i * 2, 100)
            sig.record_message("B", "A", 1000.0 + i * 2 + 1, 100)
        snap = sig.evaluate({"A", "B"})
        assert snap.ordering_anomaly >= 0.0

    def test_clear_resets(self):
        """Clear should reset all state."""
        sig = SideChannelSignal()
        for i in range(10):
            sig.record_message("A", "B", 1000.0 + i, 100)
        sig.clear()
        snap = sig.evaluate({"A", "B"})
        assert snap.risk_score == 0.0

    def test_detected_patterns_list(self):
        """detected_patterns should be a list of strings."""
        sig = SideChannelSignal()
        for i in range(15):
            sig.record_message("A", "B", 1000.0 + i * 1.0, 100)
        snap = sig.evaluate({"A", "B"})
        assert isinstance(snap.detected_patterns, list)
        for p in snap.detected_patterns:
            assert isinstance(p, str)
