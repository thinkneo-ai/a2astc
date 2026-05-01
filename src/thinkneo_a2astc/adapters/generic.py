"""
Generic Adapter (Section 10.4).

Direct tuple interface for custom or in-process agent communication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class NormalizedMessage:
    """Normalized message tuple for the compliance gate."""

    sender_id: str
    receiver_id: str
    payload: str
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[float] = None
    raw: Optional[Any] = None

    def to_tuple(self) -> Tuple[str, str, str, Dict[str, str]]:
        """Convert to standard (sender, receiver, payload, headers) tuple."""
        return (self.sender_id, self.receiver_id, self.payload, self.headers)


class GenericAdapter:
    """Generic adapter that accepts direct (sender, receiver, payload, headers) tuples.

    Use this adapter when you have direct control over the message format
    or when building a custom integration.
    """

    def __init__(self) -> None:
        self._message_count: int = 0

    def normalize(
        self,
        sender_id: str,
        receiver_id: str,
        payload: str | bytes = "",
        headers: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ) -> NormalizedMessage:
        """Normalize a direct message into the standard format.

        Args:
            sender_id: Sending agent identifier.
            receiver_id: Receiving agent identifier.
            payload: Message payload (string or bytes).
            headers: Optional message headers.
            timestamp: Optional message timestamp.

        Returns:
            NormalizedMessage in the standard format.
        """
        self._message_count += 1

        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")

        return NormalizedMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload=payload,
            headers=headers or {},
            timestamp=timestamp,
        )

    def from_dict(self, data: Dict[str, Any]) -> NormalizedMessage:
        """Create a normalized message from a dictionary.

        Expected keys: sender_id, receiver_id, payload.
        Optional keys: headers, timestamp.
        """
        self._message_count += 1

        return NormalizedMessage(
            sender_id=str(data.get("sender_id", "unknown")),
            receiver_id=str(data.get("receiver_id", "unknown")),
            payload=str(data.get("payload", "")),
            headers=data.get("headers", {}),
            timestamp=data.get("timestamp"),
            raw=data,
        )

    @property
    def message_count(self) -> int:
        """Total messages processed by this adapter."""
        return self._message_count
