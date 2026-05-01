"""Tests for TeamAuditTrail (Section 9)."""

import time
import pytest
from thinkneo_a2astc.trail import TeamAuditTrail, EventType, AuditEntry, GENESIS_HASH
from thinkneo_a2astc.config import A2ASTCConfig


class TestAppendOnly:
    """Tests for append-only behavior."""

    def test_initial_empty(self):
        """New trail should be empty."""
        trail = TeamAuditTrail()
        assert trail.get_entry_count() == 0

    def test_record_adds_entry(self):
        """Recording should add an entry."""
        trail = TeamAuditTrail()
        trail.record_event(
            EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], ""
        )
        assert trail.get_entry_count() == 1

    def test_entries_monotonically_increase(self):
        """Entry count should only increase."""
        trail = TeamAuditTrail()
        counts = []
        for i in range(5):
            trail.record_event(
                EventType.TEAM_GATE_VERDICT, "t1", 1, 0.0, "ALLOW", [], ""
            )
            counts.append(trail.get_entry_count())
        assert counts == sorted(counts)
        assert counts == [1, 2, 3, 4, 5]

    def test_get_last_entry(self):
        """Should return the most recent entry."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.1, "WARN", [], "")
        last = trail.get_last_entry()
        assert last.event_type == EventType.TEAM_GATE_VERDICT

    def test_get_last_entry_empty(self):
        """Should return None for empty trail."""
        trail = TeamAuditTrail()
        assert trail.get_last_entry() is None


class TestHashChain:
    """Tests for SHA-256 hash chain."""

    def test_first_entry_uses_genesis(self):
        """First entry should link to genesis hash."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        entry = trail.get_last_entry()
        assert entry.prev_hash == GENESIS_HASH

    def test_chain_links_entries(self):
        """Each entry should link to the previous entry's hash."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        first_hash = trail.get_last_entry().entry_hash
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.1, "ALLOW", [], "")
        second = trail.get_last_entry()
        assert second.prev_hash == first_hash

    def test_validate_valid_chain(self):
        """Valid chain should pass validation."""
        trail = TeamAuditTrail()
        for i in range(10):
            trail.record_event(
                EventType.TEAM_GATE_VERDICT, "t1", i + 1, 0.0, "ALLOW", [], ""
            )
        valid, broken = trail.validate_chain()
        assert valid is True
        assert broken is None

    def test_validate_empty_chain(self):
        """Empty chain should be valid."""
        trail = TeamAuditTrail()
        valid, broken = trail.validate_chain()
        assert valid is True

    def test_detect_tamper(self):
        """Tampered entry should be detected."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.5, "WARN", [], "")
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 3, 0.1, "ALLOW", [], "")

        # Tamper with second entry
        trail._entries[1].verdict = "ALLOW"  # Change from WARN to ALLOW

        valid, broken = trail.validate_chain()
        assert valid is False
        assert broken == 1

    def test_hashes_are_sha256(self):
        """Entry hashes should be 64 hex characters (SHA-256)."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        entry = trail.get_last_entry()
        assert len(entry.entry_hash) == 64
        assert all(c in "0123456789abcdef" for c in entry.entry_hash)


class TestEventTypes:
    """Tests for required event types."""

    def test_all_event_types_recordable(self):
        """All event types should be recordable."""
        trail = TeamAuditTrail()
        for et in EventType:
            trail.record_event(et, "t1", 1, 0.0, "ALLOW", [], "")
        assert trail.get_entry_count() == len(EventType)

    def test_filter_by_event_type(self):
        """Should filter entries by event type."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.0, "ALLOW", [], "")
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 3, 0.0, "WARN", [], "")

        results = trail.get_entries(event_type=EventType.TEAM_GATE_VERDICT)
        assert len(results) == 2

    def test_filter_by_team_id(self):
        """Should filter entries by team ID."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        trail.record_event(EventType.TEAM_FORMED, "t2", 1, 0.0, "ALLOW", [], "")
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.0, "ALLOW", [], "")

        results = trail.get_entries(team_id="t1")
        assert len(results) == 2


class TestTrailRetention:
    """Tests for retention policy."""

    def test_prune_old_entries(self):
        """Should prune entries older than retention period."""
        cfg = A2ASTCConfig(trail_retention_days=1)
        trail = TeamAuditTrail(cfg)

        # Old entry
        trail.record_event(
            EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "",
            timestamp=1000.0,
        )
        # Recent entry
        trail.record_event(
            EventType.TEAM_GATE_VERDICT, "t1", 2, 0.0, "ALLOW", [], "",
            timestamp=time.time(),
        )

        pruned = trail.prune_expired()
        assert pruned == 1
        assert trail.get_entry_count() == 1

    def test_no_prune_recent(self):
        """Should not prune recent entries."""
        cfg = A2ASTCConfig(trail_retention_days=365)
        trail = TeamAuditTrail(cfg)
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        pruned = trail.prune_expired()
        assert pruned == 0


class TestTrailSerialization:
    """Tests for trail import/export."""

    def test_export_entries(self):
        """Should export entries as dicts."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        exported = trail.export_entries()
        assert len(exported) == 1
        assert exported[0]["event_type"] == "TEAM_FORMED"

    def test_import_entries(self):
        """Should import entries maintaining chain."""
        trail1 = TeamAuditTrail()
        trail1.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        trail1.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.1, "ALLOW", [], "")
        exported = trail1.export_entries()

        trail2 = TeamAuditTrail()
        count = trail2.import_entries(exported)
        assert count == 2

        valid, _ = trail2.validate_chain()
        assert valid

    def test_entry_from_dict(self):
        """AuditEntry should deserialize from dict."""
        trail = TeamAuditTrail()
        trail.record_event(
            EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW",
            [("A", "B")], "payload-hash"
        )
        d = trail.get_last_entry().to_dict()
        entry = AuditEntry.from_dict(d)
        assert entry.team_id == "t1"
        assert len(entry.affected_edges) == 1

    def test_clear_resets_to_genesis(self):
        """Clear should reset to genesis hash."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "")
        trail.clear()
        assert trail.get_entry_count() == 0
        assert trail.get_last_hash() == GENESIS_HASH

    def test_query_with_limit(self):
        """Should respect query limit."""
        trail = TeamAuditTrail()
        for i in range(10):
            trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", i, 0.0, "ALLOW", [], "")
        results = trail.get_entries(limit=3)
        assert len(results) == 3

    def test_query_with_time_range(self):
        """Should filter by time range."""
        trail = TeamAuditTrail()
        trail.record_event(EventType.TEAM_FORMED, "t1", 1, 0.0, "ALLOW", [], "", timestamp=1000.0)
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 2, 0.0, "ALLOW", [], "", timestamp=2000.0)
        trail.record_event(EventType.TEAM_GATE_VERDICT, "t1", 3, 0.0, "ALLOW", [], "", timestamp=3000.0)
        results = trail.get_entries(since=1500.0, until=2500.0)
        assert len(results) == 1
