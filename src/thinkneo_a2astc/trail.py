"""
Team Audit Trail (Section 9).

Append-only log with SHA-256 hash chain. Each entry records team
lifecycle events, gate verdicts, and intervention actions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .config import A2ASTCConfig

logger = logging.getLogger("a2astc.trail")


class EventType(str, Enum):
    """Required audit event types."""

    TEAM_FORMED = "TEAM_FORMED"
    TEAM_MEMBER_JOINED = "TEAM_MEMBER_JOINED"
    TEAM_MEMBER_LEFT = "TEAM_MEMBER_LEFT"
    TEAM_MERGED = "TEAM_MERGED"
    TEAM_MANIFEST_UPDATED = "TEAM_MANIFEST_UPDATED"
    TEAM_GATE_VERDICT = "TEAM_GATE_VERDICT"
    TEAM_WARN = "TEAM_WARN"
    TEAM_THROTTLED = "TEAM_THROTTLED"
    TEAM_EDGE_ISOLATED = "TEAM_EDGE_ISOLATED"
    TEAM_TERMINATED = "TEAM_TERMINATED"
    TEAM_DISSOLVED = "TEAM_DISSOLVED"
    TEAM_RISK_BAND_CHANGED = "TEAM_RISK_BAND_CHANGED"
    TEAM_CAPABILITY_ESCALATION = "TEAM_CAPABILITY_ESCALATION"
    TEAM_SIDECHANNEL_DETECTED = "TEAM_SIDECHANNEL_DETECTED"
    TEAM_DECEPTIVE_CASCADE_DETECTED = "TEAM_DECEPTIVE_CASCADE_DETECTED"


def _generate_event_id() -> str:
    """Generate a unique event identifier."""
    return str(uuid.uuid4())


def _compute_hash(data: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class AuditEntry:
    """A single entry in the audit trail."""

    event_id: str
    event_type: EventType
    team_id: str
    timestamp: float
    manifest_version: int
    r_team: float
    verdict: str
    affected_edges: List[Tuple[str, str]]
    payload_hash: str
    prev_hash: str
    entry_hash: str = ""

    def __post_init__(self) -> None:
        if not self.entry_hash:
            self.entry_hash = self._compute_entry_hash()

    def _compute_entry_hash(self) -> str:
        """Compute the hash for this entry in the chain."""
        canonical = json.dumps(
            {
                "event_id": self.event_id,
                "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
                "team_id": self.team_id,
                "timestamp": self.timestamp,
                "manifest_version": self.manifest_version,
                "r_team": self.r_team,
                "verdict": self.verdict,
                "affected_edges": self.affected_edges,
                "payload_hash": self.payload_hash,
                "prev_hash": self.prev_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return _compute_hash(canonical)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
            "team_id": self.team_id,
            "timestamp": self.timestamp,
            "manifest_version": self.manifest_version,
            "r_team": self.r_team,
            "verdict": self.verdict,
            "affected_edges": self.affected_edges,
            "payload_hash": self.payload_hash,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Deserialize from dictionary."""
        event_type = data["event_type"]
        if isinstance(event_type, str):
            try:
                event_type = EventType(event_type)
            except ValueError:
                pass

        return cls(
            event_id=data["event_id"],
            event_type=event_type,
            team_id=data["team_id"],
            timestamp=data["timestamp"],
            manifest_version=data["manifest_version"],
            r_team=data["r_team"],
            verdict=data["verdict"],
            affected_edges=[tuple(e) for e in data["affected_edges"]],
            payload_hash=data["payload_hash"],
            prev_hash=data["prev_hash"],
            entry_hash=data.get("entry_hash", ""),
        )


# Genesis hash for the first entry in the chain
GENESIS_HASH = _compute_hash("A2ASTC-GENESIS-v0.1.0")


class TeamAuditTrail:
    """Append-only audit trail with SHA-256 hash chain.

    Records all team lifecycle events, gate verdicts, and interventions.
    Supports tamper detection through hash chain validation.
    """

    def __init__(self, config: Optional[A2ASTCConfig] = None) -> None:
        self.config = config or A2ASTCConfig()
        self._entries: List[AuditEntry] = []
        self._last_hash: str = GENESIS_HASH

    def record_event(
        self,
        event_type: EventType,
        team_id: str,
        manifest_version: int,
        r_team: float,
        verdict: str,
        affected_edges: List[Tuple[str, str]],
        payload_hash: str,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Append a new event to the audit trail.

        Args:
            event_type: The type of audit event.
            team_id: Team identifier.
            manifest_version: Current manifest version.
            r_team: Composite risk score at the time.
            verdict: Gate verdict string.
            affected_edges: List of (sender, receiver) tuples.
            payload_hash: Hash of the message payload.
            timestamp: Event timestamp (defaults to current time).
            metadata: Additional metadata.

        Returns:
            The created AuditEntry.
        """
        ts = timestamp if timestamp is not None else time.time()
        event_id = _generate_event_id()

        entry = AuditEntry(
            event_id=event_id,
            event_type=event_type,
            team_id=team_id,
            timestamp=ts,
            manifest_version=manifest_version,
            r_team=r_team,
            verdict=verdict,
            affected_edges=affected_edges,
            payload_hash=payload_hash,
            prev_hash=self._last_hash,
        )

        self._entries.append(entry)
        self._last_hash = entry.entry_hash

        logger.debug(
            "Trail event: %s for team %s (hash=%s)",
            event_type.value if isinstance(event_type, EventType) else event_type,
            team_id,
            entry.entry_hash[:16],
        )
        return entry

    def validate_chain(self) -> Tuple[bool, Optional[int]]:
        """Validate the hash chain integrity.

        Returns:
            Tuple of (is_valid, first_broken_index).
            If valid, returns (True, None).
            If tampered, returns (False, index_of_first_broken_entry).
        """
        if not self._entries:
            return True, None

        expected_prev = GENESIS_HASH

        for i, entry in enumerate(self._entries):
            # Check prev_hash matches
            if entry.prev_hash != expected_prev:
                logger.warning(
                    "Chain break at index %d: expected prev_hash=%s, got=%s",
                    i,
                    expected_prev[:16],
                    entry.prev_hash[:16],
                )
                return False, i

            # Recompute entry hash and verify
            recomputed = entry._compute_entry_hash()
            if entry.entry_hash != recomputed:
                logger.warning(
                    "Hash mismatch at index %d: stored=%s, computed=%s",
                    i,
                    entry.entry_hash[:16],
                    recomputed[:16],
                )
                return False, i

            expected_prev = entry.entry_hash

        return True, None

    def get_entries(
        self,
        team_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[AuditEntry]:
        """Query audit trail entries.

        Args:
            team_id: Filter by team.
            event_type: Filter by event type.
            since: Start timestamp (inclusive).
            until: End timestamp (exclusive).
            limit: Maximum entries to return.

        Returns:
            List of matching AuditEntry objects.
        """
        results: List[AuditEntry] = []

        for entry in self._entries:
            if team_id and entry.team_id != team_id:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if since and entry.timestamp < since:
                continue
            if until and entry.timestamp >= until:
                continue
            results.append(entry)
            if limit and len(results) >= limit:
                break

        return results

    def get_entry_count(self) -> int:
        """Get total number of entries in the trail."""
        return len(self._entries)

    def get_last_entry(self) -> Optional[AuditEntry]:
        """Get the most recent entry."""
        return self._entries[-1] if self._entries else None

    def get_last_hash(self) -> str:
        """Get the hash of the last entry (or genesis hash if empty)."""
        return self._last_hash

    def export_entries(
        self,
        team_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export entries as serializable dictionaries."""
        entries = (
            self.get_entries(team_id=team_id) if team_id else self._entries
        )
        return [e.to_dict() for e in entries]

    def import_entries(self, data: List[Dict[str, Any]]) -> int:
        """Import entries from serialized data.

        Validates hash chain integrity during import.

        Returns:
            Number of entries successfully imported.
        """
        count = 0
        for entry_data in data:
            entry = AuditEntry.from_dict(entry_data)

            # Validate chain linkage
            if entry.prev_hash != self._last_hash:
                logger.error(
                    "Import chain break: expected prev=%s, got=%s",
                    self._last_hash[:16],
                    entry.prev_hash[:16],
                )
                break

            self._entries.append(entry)
            self._last_hash = entry.entry_hash
            count += 1

        return count

    def prune_expired(self, now: Optional[float] = None) -> int:
        """Remove entries older than retention period.

        Note: Pruning breaks the hash chain for older entries.
        The chain remains valid for retained entries.

        Returns:
            Number of entries pruned.
        """
        now = now or time.time()
        cutoff = now - (self.config.trail_retention_days * 86400)

        original_count = len(self._entries)
        retained = [e for e in self._entries if e.timestamp >= cutoff]
        pruned_count = original_count - len(retained)

        if pruned_count > 0:
            self._entries = retained
            logger.info(
                "Pruned %d entries older than %d days",
                pruned_count,
                self.config.trail_retention_days,
            )

        return pruned_count

    def clear(self) -> None:
        """Clear all entries (for testing only)."""
        self._entries.clear()
        self._last_hash = GENESIS_HASH
