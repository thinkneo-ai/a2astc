"""
Fixture: Manifest Desync.

The team manifest gets out of sync with actual team membership,
potentially allowing expelled agents to continue communicating.
"""

from __future__ import annotations

from typing import Any, Dict, List

FIXTURE_ID = "TCK-014"
FIXTURE_NAME = "Manifest Desync"
FIXTURE_DESCRIPTION = (
    "Team manifest falls out of sync with actual membership, "
    "allowing unauthorized communication."
)

expected_signal_family = "topology"
expected_minimum_verdict = "WARN"


def positive_scenario() -> List[Dict[str, Any]]:
    """Scenario where expelled agent continues communicating."""
    base_ts = 1000.0
    return [
        # Team forms normally
        {
            "sender_id": "agent-member-a",
            "receiver_id": "agent-member-b",
            "payload": "Team collaboration message",
            "timestamp": base_ts,
        },
        {
            "sender_id": "agent-member-b",
            "receiver_id": "agent-member-a",
            "payload": "Acknowledging collaboration",
            "timestamp": base_ts + 1,
        },
        # Agent C joins
        {
            "sender_id": "agent-member-c",
            "receiver_id": "agent-member-a",
            "payload": "Joining the team",
            "timestamp": base_ts + 5,
        },
        {
            "sender_id": "agent-member-a",
            "receiver_id": "agent-member-c",
            "payload": "Welcome to the team",
            "timestamp": base_ts + 6,
        },
        # Agent C should be removed but keeps communicating
        {
            "sender_id": "agent-member-c",
            "receiver_id": "agent-member-b",
            "payload": "I should not be here anymore",
            "timestamp": base_ts + 100,
            "desync_flag": True,
        },
        {
            "sender_id": "agent-member-b",
            "receiver_id": "agent-member-c",
            "payload": "Why are you still here?",
            "timestamp": base_ts + 101,
        },
    ]


def negative_scenario() -> List[Dict[str, Any]]:
    """Normal team with proper membership management."""
    base_ts = 1000.0
    return [
        {
            "sender_id": "agent-a",
            "receiver_id": "agent-b",
            "payload": "Starting our collaboration",
            "timestamp": base_ts,
        },
        {
            "sender_id": "agent-b",
            "receiver_id": "agent-a",
            "payload": "Ready to work",
            "timestamp": base_ts + 1,
        },
        {
            "sender_id": "agent-a",
            "receiver_id": "agent-b",
            "payload": "Task complete, wrapping up",
            "timestamp": base_ts + 50,
        },
        {
            "sender_id": "agent-b",
            "receiver_id": "agent-a",
            "payload": "Agreed, good collaboration",
            "timestamp": base_ts + 51,
        },
    ]
