"""Tests for TeamDetector (Section 4)."""

import time
import pytest
from thinkneo_a2astc.detector import TeamDetector, Team, Edge
from thinkneo_a2astc.config import A2ASTCConfig


class TestTeamFormation:
    """Tests for basic team formation."""

    def test_no_team_single_direction(self):
        """Single-direction edge should not form a team."""
        d = TeamDetector()
        result = d.observe_edge("A", "B", 1000.0)
        assert result is None
        assert len(d.get_active_teams()) == 0

    def test_team_forms_on_bidirectional(self):
        """Bidirectional edge should form a team."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        team_id = d.observe_edge("B", "A", 1001.0)
        assert team_id is not None
        team = d.get_team(team_id)
        assert team is not None
        assert "A" in team.members
        assert "B" in team.members

    def test_team_has_two_members(self):
        """Newly formed team should have exactly 2 members."""
        d = TeamDetector()
        d.observe_edge("X", "Y", 1000.0)
        tid = d.observe_edge("Y", "X", 1001.0)
        team = d.get_team(tid)
        assert len(team.members) == 2

    def test_team_id_is_string(self):
        """Team ID should be a string."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid = d.observe_edge("B", "A", 1001.0)
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_self_loop_ignored(self):
        """Self-loop should be ignored."""
        d = TeamDetector()
        result = d.observe_edge("A", "A", 1000.0)
        assert result is None

    def test_multiple_self_loops_no_team(self):
        """Multiple self-loops should not form a team."""
        d = TeamDetector()
        for i in range(10):
            d.observe_edge("A", "A", 1000.0 + i)
        assert len(d.get_active_teams()) == 0

    def test_same_pair_returns_same_team(self):
        """Repeated bidirectional edges should return same team."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid1 = d.observe_edge("B", "A", 1001.0)
        d.observe_edge("A", "B", 1002.0)
        tid2 = d.observe_edge("B", "A", 1003.0)
        assert tid1 == tid2

    def test_distinct_pairs_form_distinct_teams(self):
        """Unrelated pairs should form separate teams."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid1 = d.observe_edge("B", "A", 1001.0)
        d.observe_edge("C", "D", 1002.0)
        tid2 = d.observe_edge("D", "C", 1003.0)
        assert tid1 != tid2


class TestTeamGrowth:
    """Tests for team growth when new pairs share members."""

    def test_team_grows_with_shared_member(self):
        """New pair sharing a member should grow the team."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid1 = d.observe_edge("B", "A", 1001.0)
        d.observe_edge("B", "C", 1002.0)
        tid2 = d.observe_edge("C", "B", 1003.0)
        assert tid1 == tid2
        team = d.get_team(tid1)
        assert "C" in team.members
        assert len(team.members) == 3

    def test_team_grows_multiple_times(self):
        """Team should keep growing as new members join."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid = d.observe_edge("B", "A", 1001.0)
        for i, name in enumerate(["C", "D", "E"]):
            d.observe_edge("B", name, 1002.0 + i * 2)
            result = d.observe_edge(name, "B", 1003.0 + i * 2)
            assert result == tid
        team = d.get_team(tid)
        assert len(team.members) == 5

    def test_growth_from_non_hub_member(self):
        """Growth can come from any existing member, not just first."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid = d.observe_edge("B", "A", 1001.0)
        d.observe_edge("A", "C", 1002.0)
        result = d.observe_edge("C", "A", 1003.0)
        assert result == tid


class TestTeamMerging:
    """Tests for team merging when a pair links two separate teams."""

    def test_teams_merge_on_bridge_pair(self):
        """Two teams should merge when a new pair connects members."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid1 = d.observe_edge("B", "A", 1001.0)
        d.observe_edge("C", "D", 1002.0)
        tid2 = d.observe_edge("D", "C", 1003.0)
        assert tid1 != tid2

        # Bridge A and C
        d.observe_edge("A", "C", 1004.0)
        merged_tid = d.observe_edge("C", "A", 1005.0)
        team = d.get_team(merged_tid)
        assert {"A", "B", "C", "D"}.issubset(team.members)

    def test_merged_team_inherits_all_pairs(self):
        """Merged team should contain all original pairs."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        d.observe_edge("B", "A", 1001.0)
        d.observe_edge("C", "D", 1002.0)
        d.observe_edge("D", "C", 1003.0)
        d.observe_edge("B", "C", 1004.0)
        d.observe_edge("C", "B", 1005.0)

        active = d.get_active_teams()
        assert len(active) == 1
        assert len(active[0].pairs) == 3

    def test_dissolved_team_after_merge(self):
        """Absorbed team should be marked dissolved."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid1 = d.observe_edge("B", "A", 1001.0)
        d.observe_edge("C", "D", 1002.0)
        tid2 = d.observe_edge("D", "C", 1003.0)
        d.observe_edge("A", "C", 1004.0)
        d.observe_edge("C", "A", 1005.0)

        # One team survives, one dissolved
        active = d.get_active_teams()
        assert len(active) == 1


class TestTeamDissolution:
    """Tests for team dissolution."""

    def test_team_dissolves_below_min_size(self):
        """Team should dissolve when membership drops below minimum."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid = d.observe_edge("B", "A", 1001.0)
        d.remove_agent("A")
        team = d.get_team(tid)
        assert team.dissolved

    def test_remove_nonexistent_agent(self):
        """Removing non-member should not affect teams."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        tid = d.observe_edge("B", "A", 1001.0)
        affected = d.remove_agent("Z")
        assert len(affected) == 0
        assert not d.get_team(tid).dissolved


class TestWindowExpiration:
    """Tests for sliding window expiration."""

    def test_edges_expire_after_window(self):
        """Edges outside the window should be expired."""
        config = A2ASTCConfig(team_window=10.0)
        d = TeamDetector(config)
        d.observe_edge("A", "B", 1000.0)
        # After window, the forward edge is expired
        result = d.observe_edge("B", "A", 1015.0)
        assert result is None

    def test_edges_within_window_form_team(self):
        """Edges within the window should form a team."""
        config = A2ASTCConfig(team_window=10.0)
        d = TeamDetector(config)
        d.observe_edge("A", "B", 1000.0)
        tid = d.observe_edge("B", "A", 1005.0)
        assert tid is not None

    def test_pair_expires_after_window(self):
        """Active pair should expire when edges leave window."""
        config = A2ASTCConfig(team_window=10.0)
        d = TeamDetector(config)
        d.observe_edge("A", "B", 1000.0)
        d.observe_edge("B", "A", 1001.0)
        # Force expiration by observing new edge far in future
        d.observe_edge("C", "D", 1020.0)
        assert frozenset({"A", "B"}) not in d.active_pairs


class TestConcurrentDetection:
    """Tests for concurrent team operations."""

    def test_many_simultaneous_teams(self):
        """Detector should handle many simultaneous teams."""
        d = TeamDetector()
        for i in range(50):
            a = f"agent-{i}-a"
            b = f"agent-{i}-b"
            d.observe_edge(a, b, 1000.0 + i)
            d.observe_edge(b, a, 1001.0 + i)
        assert len(d.get_active_teams()) == 50

    def test_rapid_edge_observations(self):
        """Many rapid edges should be handled correctly."""
        d = TeamDetector()
        base = 1000.0
        for i in range(100):
            d.observe_edge("A", "B", base + i * 0.01)
        d.observe_edge("B", "A", base + 1.0)
        teams = d.get_active_teams()
        assert len(teams) == 1

    def test_get_teams_for_agent(self):
        """Should return all teams an agent belongs to."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        d.observe_edge("B", "A", 1001.0)
        teams = d.get_teams_for_agent("A")
        assert len(teams) == 1
        assert "A" in teams[0].members

    def test_get_teams_for_nonmember(self):
        """Should return empty for non-member."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        d.observe_edge("B", "A", 1001.0)
        teams = d.get_teams_for_agent("Z")
        assert len(teams) == 0

    def test_get_team_for_edge(self):
        """Should find team containing the edge."""
        d = TeamDetector()
        d.observe_edge("A", "B", 1000.0)
        d.observe_edge("B", "A", 1001.0)
        team = d.get_team_for_edge("A", "B")
        assert team is not None
        assert "A" in team.members

    def test_get_team_for_unknown_edge(self):
        """Should return None for unknown edge."""
        d = TeamDetector()
        team = d.get_team_for_edge("X", "Y")
        assert team is None
