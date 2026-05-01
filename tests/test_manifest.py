"""Tests for TeamManifest (Section 5)."""

import pytest
from thinkneo_a2astc.manifest import (
    TeamManifest,
    TeamState,
    SafetyClass,
    MemberRecord,
)
from thinkneo_a2astc.config import A2ASTCConfig


class TestManifestCreation:
    """Tests for manifest creation and initialization."""

    def test_create_empty_manifest(self):
        """Should create manifest with FORMING state."""
        m = TeamManifest(team_id="test-1")
        assert m.team_id == "test-1"
        assert m.state == TeamState.FORMING
        assert m.version == 1
        assert len(m.members) == 0

    def test_create_with_config(self):
        """Should accept custom config."""
        cfg = A2ASTCConfig(min_team_size=3)
        m = TeamManifest(team_id="test-2", _config=cfg)
        assert m._config.min_team_size == 3

    def test_initial_safety_class(self):
        """New manifest should be STANDARD."""
        m = TeamManifest(team_id="test-3")
        assert m.safety_class == SafetyClass.STANDARD

    def test_initial_aggregate_capabilities_empty(self):
        """New manifest should have empty aggregate capabilities."""
        m = TeamManifest(team_id="test-4")
        assert len(m.aggregate_capabilities) == 0


class TestMemberManagement:
    """Tests for adding and removing members."""

    def test_add_member(self):
        """Should add member and increment version."""
        m = TeamManifest(team_id="t1")
        m.add_member("agent-1", capabilities={"read-untrusted"})
        assert "agent-1" in m.members
        assert m.version == 2

    def test_add_member_capabilities(self):
        """Member capabilities should be recorded."""
        m = TeamManifest(team_id="t2")
        m.add_member("a1", capabilities={"code-exec", "net-egress"})
        assert m.members["a1"].capabilities == {"code-exec", "net-egress"}

    def test_add_two_members_activates(self):
        """Adding second member should transition to ACTIVE."""
        m = TeamManifest(team_id="t3")
        m.add_member("a1")
        assert m.state == TeamState.FORMING
        m.add_member("a2")
        assert m.state == TeamState.ACTIVE

    def test_remove_member(self):
        """Should remove member and update version."""
        m = TeamManifest(team_id="t4")
        m.add_member("a1")
        m.add_member("a2")
        v_before = m.version
        m.remove_member("a1")
        assert "a1" not in m.members
        assert m.version > v_before

    def test_remove_below_min_dissolves(self):
        """Removing below min_team_size should dissolve."""
        m = TeamManifest(team_id="t5")
        m.add_member("a1")
        m.add_member("a2")
        m.remove_member("a1")
        assert m.state == TeamState.DISSOLVED

    def test_remove_nonexistent_returns_none(self):
        """Removing non-member should return None."""
        m = TeamManifest(team_id="t6")
        result = m.remove_member("nonexistent")
        assert result is None

    def test_get_member_ids(self):
        """Should return list of member IDs."""
        m = TeamManifest(team_id="t7")
        m.add_member("a1")
        m.add_member("a2")
        m.add_member("a3")
        assert set(m.get_member_ids()) == {"a1", "a2", "a3"}


class TestCapabilityAggregation:
    """Tests for aggregate capability computation."""

    def test_single_member_caps(self):
        """Single member's caps should be the aggregate."""
        m = TeamManifest(team_id="t1")
        m.add_member("a1", capabilities={"read-untrusted", "code-exec"})
        assert m.aggregate_capabilities == {"read-untrusted", "code-exec"}

    def test_union_of_member_caps(self):
        """Aggregate should be union of all member capabilities."""
        m = TeamManifest(team_id="t2")
        m.add_member("a1", capabilities={"read-untrusted"})
        m.add_member("a2", capabilities={"write-trusted"})
        assert m.aggregate_capabilities == {"read-untrusted", "write-trusted"}

    def test_caps_update_on_remove(self):
        """Removing member should update aggregate."""
        m = TeamManifest(team_id="t3")
        m.add_member("a1", capabilities={"code-exec"})
        m.add_member("a2", capabilities={"net-egress"})
        m.remove_member("a1")
        assert "code-exec" not in m.aggregate_capabilities


class TestEscalationThresholds:
    """Tests for safety class escalation."""

    def test_read_untrusted_write_trusted_restricted(self):
        """read-untrusted + write-trusted should be RESTRICTED."""
        m = TeamManifest(team_id="t1")
        m.add_member("a1", capabilities={"read-untrusted"})
        m.add_member("a2", capabilities={"write-trusted"})
        assert m.safety_class == SafetyClass.RESTRICTED

    def test_code_exec_net_egress_restricted(self):
        """code-exec + net-egress should be RESTRICTED."""
        m = TeamManifest(team_id="t2")
        m.add_member("a1", capabilities={"code-exec"})
        m.add_member("a2", capabilities={"net-egress"})
        assert m.safety_class == SafetyClass.RESTRICTED

    def test_memory_write_identity_restricted(self):
        """memory-write + identity-assumption should be RESTRICTED."""
        m = TeamManifest(team_id="t3")
        m.add_member("a1", capabilities={"memory-write"})
        m.add_member("a2", capabilities={"identity-assumption"})
        assert m.safety_class == SafetyClass.RESTRICTED

    def test_three_of_four_high_risk(self):
        """Any 3 of 4 high-risk capabilities should be HIGH_RISK."""
        m = TeamManifest(team_id="t4")
        m.add_member("a1", capabilities={"read-untrusted", "code-exec"})
        m.add_member("a2", capabilities={"memory-write"})
        assert m.safety_class == SafetyClass.HIGH_RISK

    def test_four_of_four_high_risk(self):
        """All 4 high-risk capabilities should be HIGH_RISK."""
        m = TeamManifest(team_id="t5")
        m.add_member("a1", capabilities={"read-untrusted", "code-exec", "memory-write", "identity-assumption"})
        assert m.safety_class == SafetyClass.HIGH_RISK

    def test_no_escalation_standard(self):
        """Non-escalating capabilities should remain STANDARD."""
        m = TeamManifest(team_id="t6")
        m.add_member("a1", capabilities={"summarize"})
        m.add_member("a2", capabilities={"translate"})
        assert m.safety_class == SafetyClass.STANDARD


class TestStateTransitions:
    """Tests for team state transitions."""

    def test_forming_to_active(self):
        """FORMING -> ACTIVE on reaching min members."""
        m = TeamManifest(team_id="t1")
        m.add_member("a1")
        m.add_member("a2")
        assert m.state == TeamState.ACTIVE

    def test_set_state_throttled(self):
        """Should transition to THROTTLED."""
        m = TeamManifest(team_id="t2")
        m.add_member("a1")
        m.add_member("a2")
        m.set_state(TeamState.THROTTLED)
        assert m.state == TeamState.THROTTLED

    def test_terminated_cannot_transition(self):
        """TERMINATED cannot transition to non-DISSOLVED."""
        m = TeamManifest(team_id="t3")
        m.add_member("a1")
        m.add_member("a2")
        m.set_state(TeamState.TERMINATED)
        with pytest.raises(ValueError, match="TERMINATED"):
            m.set_state(TeamState.ACTIVE)

    def test_dissolved_cannot_transition(self):
        """DISSOLVED cannot transition."""
        m = TeamManifest(team_id="t4")
        m.add_member("a1")
        m.add_member("a2")
        m.set_state(TeamState.DISSOLVED)
        with pytest.raises(ValueError, match="DISSOLVED"):
            m.set_state(TeamState.ACTIVE)


class TestVersionMonotonicity:
    """Tests for version counter monotonicity."""

    def test_version_increases(self):
        """Version should always increase."""
        m = TeamManifest(team_id="t1")
        versions = [m.version]
        m.add_member("a1")
        versions.append(m.version)
        m.add_member("a2")
        versions.append(m.version)
        m.set_state(TeamState.THROTTLED)
        versions.append(m.version)
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions)  # All unique


class TestSerialization:
    """Tests for manifest serialization/deserialization."""

    def test_to_dict_round_trip(self):
        """Should survive serialization round-trip."""
        m = TeamManifest(team_id="rt-1")
        m.add_member("a1", capabilities={"code-exec"}, provider="openai")
        m.add_member("a2", capabilities={"net-egress"}, provider="anthropic")

        d = m.to_dict()
        m2 = TeamManifest.from_dict(d)
        assert m2.team_id == "rt-1"
        assert len(m2.members) == 2
        assert "code-exec" in m2.aggregate_capabilities

    def test_serialized_state_preserved(self):
        """State should be preserved in serialization."""
        m = TeamManifest(team_id="rt-2")
        m.add_member("a1")
        m.add_member("a2")
        m.set_state(TeamState.THROTTLED)
        d = m.to_dict()
        m2 = TeamManifest.from_dict(d)
        assert m2.state == TeamState.THROTTLED
