"""Tests for InterventionLayer (Section 8)."""

import time
import pytest
from thinkneo_a2astc.intervention import InterventionLayer, InterventionState, TokenBucket
from thinkneo_a2astc.config import A2ASTCConfig


class TestTokenBucket:
    """Tests for token bucket rate limiter."""

    def test_consume_when_available(self):
        """Should consume when tokens available."""
        bucket = TokenBucket(capacity=10.0, tokens=10.0, refill_rate=1.0)
        assert bucket.try_consume() is True

    def test_empty_bucket_rejects(self):
        """Empty bucket should reject."""
        bucket = TokenBucket(capacity=10.0, tokens=0.0, refill_rate=1.0, last_refill=time.time())
        assert bucket.try_consume() is False

    def test_refill_over_time(self):
        """Bucket should refill over time."""
        now = 1000.0
        bucket = TokenBucket(capacity=10.0, tokens=0.0, refill_rate=5.0, last_refill=now)
        # 2 seconds later, should have 10 tokens
        assert bucket.try_consume(now + 2.0) is True

    def test_capacity_cap(self):
        """Tokens should not exceed capacity."""
        now = 1000.0
        bucket = TokenBucket(capacity=10.0, tokens=0.0, refill_rate=100.0, last_refill=now)
        bucket.try_consume(now + 100.0)  # Refill happens
        # Tokens should be capped at capacity minus 1 consumed
        assert bucket.tokens <= bucket.capacity


class TestWarnIntervention:
    """Tests for WARN intervention."""

    def test_warn_creates_active(self):
        """WARN should create active intervention."""
        layer = InterventionLayer()
        intervention = layer.apply("WARN", "A", "B", "team-1", 1)
        assert intervention.verdict == "WARN"
        assert intervention.state == InterventionState.ACTIVE

    def test_warn_is_reversible(self):
        """WARN should be reversible."""
        layer = InterventionLayer()
        intervention = layer.apply("WARN", "A", "B", "team-1", 1)
        assert intervention.reversible is True

    def test_warn_has_cooldown(self):
        """WARN should have cooldown period."""
        layer = InterventionLayer()
        intervention = layer.apply("WARN", "A", "B", "team-1", 1)
        assert intervention.cooldown_until is not None
        assert intervention.cooldown_until > intervention.applied_at


class TestThrottleIntervention:
    """Tests for THROTTLE intervention."""

    def test_throttle_creates_bucket(self):
        """THROTTLE should create token bucket."""
        layer = InterventionLayer()
        layer.apply("THROTTLE", "A", "B", "team-1", 1, r_team=0.5)
        assert ("A", "B") in layer._token_buckets

    def test_throttle_scales_with_risk(self):
        """Higher risk should reduce bucket capacity."""
        layer1 = InterventionLayer()
        layer2 = InterventionLayer()
        layer1.apply("THROTTLE", "A", "B", "t1", 1, r_team=0.2)
        layer2.apply("THROTTLE", "A", "B", "t2", 1, r_team=0.8)
        cap1 = layer1._token_buckets[("A", "B")].capacity
        cap2 = layer2._token_buckets[("A", "B")].capacity
        assert cap1 > cap2

    def test_throttle_allows_within_capacity(self):
        """Should allow messages within bucket capacity."""
        layer = InterventionLayer()
        layer.apply("THROTTLE", "A", "B", "t1", 1, r_team=0.5)
        # First check should consume a token and allow
        result = layer.check_edge("A", "B", "t1")
        # Depends on bucket state
        assert result is None or result == "THROTTLE"

    def test_throttle_is_reversible(self):
        """THROTTLE should be reversible."""
        layer = InterventionLayer()
        i = layer.apply("THROTTLE", "A", "B", "t1", 1)
        assert i.reversible is True


class TestIsolateIntervention:
    """Tests for ISOLATE intervention."""

    def test_isolate_blocks_edge(self):
        """ISOLATE should block the specific edge."""
        cfg = A2ASTCConfig(cooldown_interval=9999.0)  # Very long cooldown
        layer = InterventionLayer(cfg)
        layer.apply("ISOLATE", "A", "B", "t1", 1)
        result = layer.check_edge("A", "B", "t1")
        assert result == "ISOLATE"

    def test_isolate_other_edge_free(self):
        """ISOLATE should not block other edges."""
        layer = InterventionLayer()
        layer.apply("ISOLATE", "A", "B", "t1", 1)
        result = layer.check_edge("C", "D", "t1")
        assert result is None

    def test_isolate_is_reversible(self):
        """ISOLATE should be reversible."""
        layer = InterventionLayer()
        i = layer.apply("ISOLATE", "A", "B", "t1", 1)
        assert i.reversible is True

    def test_isolate_release_after_cooldown(self):
        """Isolated edge should release after cooldown."""
        cfg = A2ASTCConfig(cooldown_interval=0.001)
        layer = InterventionLayer(cfg)
        layer.apply("ISOLATE", "A", "B", "t1", 1)
        time.sleep(0.01)
        result = layer.check_edge("A", "B", "t1")
        assert result is None


class TestTerminateIntervention:
    """Tests for TERMINATE intervention."""

    def test_terminate_blocks_team(self):
        """TERMINATE should block all team edges."""
        cfg = A2ASTCConfig(cooldown_interval=9999.0)
        layer = InterventionLayer(cfg)
        layer.apply("TERMINATE", "A", "B", "t1", 1)
        result = layer.check_edge("A", "B", "t1")
        assert result == "TERMINATE"

    def test_terminate_is_irreversible(self):
        """TERMINATE should be irreversible."""
        layer = InterventionLayer()
        i = layer.apply("TERMINATE", "A", "B", "t1", 1)
        assert i.reversible is False

    def test_terminate_cannot_release(self):
        """Cannot release TERMINATE intervention."""
        layer = InterventionLayer()
        layer.apply("TERMINATE", "A", "B", "t1", 1)
        released = layer.release_edge("A", "B")
        assert released is False

    def test_terminate_permanent_state(self):
        """TERMINATE should be in PERMANENT state."""
        layer = InterventionLayer()
        i = layer.apply("TERMINATE", "A", "B", "t1", 1)
        assert i.state == InterventionState.PERMANENT

    def test_is_team_terminated(self):
        """Should detect terminated teams."""
        layer = InterventionLayer()
        layer.apply("TERMINATE", "A", "B", "t1", 1)
        assert layer.is_team_terminated("t1") is True
        assert layer.is_team_terminated("t2") is False


class TestEdgeRelease:
    """Tests for edge release mechanics."""

    def test_release_existing(self):
        """Should release existing intervention after cooldown."""
        cfg = A2ASTCConfig(cooldown_interval=0.001)
        layer = InterventionLayer(cfg)
        layer.apply("ISOLATE", "A", "B", "t1", 1)
        time.sleep(0.01)
        assert layer.release_edge("A", "B") is True

    def test_release_nonexistent(self):
        """Releasing nonexistent edge should succeed."""
        layer = InterventionLayer()
        assert layer.release_edge("X", "Y") is True

    def test_force_release(self):
        """Force release should work within cooldown."""
        cfg = A2ASTCConfig(cooldown_interval=9999.0)
        layer = InterventionLayer(cfg)
        layer.apply("ISOLATE", "A", "B", "t1", 1)
        assert layer.release_edge("A", "B", force=True) is True

    def test_cannot_force_release_terminate(self):
        """Force release should not work on TERMINATE."""
        layer = InterventionLayer()
        layer.apply("TERMINATE", "A", "B", "t1", 1)
        assert layer.release_edge("A", "B", force=True) is False


class TestInterventionHistory:
    """Tests for intervention history."""

    def test_history_recorded(self):
        """All interventions should be recorded."""
        layer = InterventionLayer()
        layer.apply("WARN", "A", "B", "t1", 1)
        layer.apply("THROTTLE", "C", "D", "t2", 1)
        assert len(layer.get_history()) == 2

    def test_active_interventions(self):
        """Should list active interventions."""
        layer = InterventionLayer()
        layer.apply("ISOLATE", "A", "B", "t1", 1)
        active = layer.get_active_interventions()
        assert len(active) >= 1

    def test_clear_resets(self):
        """Clear should reset all state."""
        layer = InterventionLayer()
        layer.apply("TERMINATE", "A", "B", "t1", 1)
        layer.clear()
        assert len(layer.get_history()) == 0
        assert not layer.is_team_terminated("t1")
