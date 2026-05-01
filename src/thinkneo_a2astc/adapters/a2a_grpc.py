"""
A2A gRPC Adapter (Section 10.4).

Extracts sender and receiver identifiers from A2A gRPC metadata.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .generic import NormalizedMessage

logger = logging.getLogger("a2astc.adapters.a2a_grpc")


class A2AGrpcAdapter:
    """Adapter for A2A over gRPC transport.

    Extracts agent identifiers from gRPC metadata headers
    following the A2A protocol conventions for gRPC.

    Expected gRPC metadata keys:
    - x-a2a-sender-agent-id: Sender agent identifier
    - x-a2a-receiver-agent-id: Receiver agent identifier
    - x-a2a-task-id: Task identifier
    """

    # Standard gRPC metadata keys for A2A
    SENDER_KEY = "x-a2a-sender-agent-id"
    RECEIVER_KEY = "x-a2a-receiver-agent-id"
    TASK_KEY = "x-a2a-task-id"

    def __init__(self) -> None:
        self._message_count: int = 0

    def normalize(
        self,
        payload: bytes | str,
        metadata: Dict[str, str] | List[Tuple[str, str]] | None = None,
        fallback_sender: str = "unknown",
        fallback_receiver: str = "unknown",
    ) -> NormalizedMessage:
        """Normalize a gRPC A2A message.

        Args:
            payload: The protobuf-serialized or text payload.
            metadata: gRPC metadata as dict or list of tuples.
            fallback_sender: Default sender if not in metadata.
            fallback_receiver: Default receiver if not in metadata.

        Returns:
            NormalizedMessage with extracted identifiers.
        """
        self._message_count += 1

        # Normalize metadata format
        meta_dict = self._normalize_metadata(metadata)

        # Extract identifiers
        sender = meta_dict.get(self.SENDER_KEY, fallback_sender)
        receiver = meta_dict.get(self.RECEIVER_KEY, fallback_receiver)

        # Convert payload
        if isinstance(payload, bytes):
            try:
                payload_str = payload.decode("utf-8")
            except UnicodeDecodeError:
                # Binary protobuf - represent as hex
                payload_str = f"<binary:{len(payload)}bytes>"
        else:
            payload_str = payload

        # Build headers
        headers = {
            "x-a2a-protocol": "a2a-0.3.0",
            "x-a2a-transport": "grpc",
        }
        task_id = meta_dict.get(self.TASK_KEY)
        if task_id:
            headers["x-a2a-task-id"] = task_id

        # Include all a2a metadata as headers
        for key, value in meta_dict.items():
            if key.startswith("x-a2a-"):
                headers[key] = value

        return NormalizedMessage(
            sender_id=sender,
            receiver_id=receiver,
            payload=payload_str,
            headers=headers,
            raw={"payload": payload, "metadata": meta_dict},
        )

    def _normalize_metadata(
        self, metadata: Dict[str, str] | List[Tuple[str, str]] | None
    ) -> Dict[str, str]:
        """Normalize gRPC metadata to a flat dictionary."""
        if metadata is None:
            return {}

        if isinstance(metadata, dict):
            return {k.lower(): v for k, v in metadata.items()}

        if isinstance(metadata, list):
            result: Dict[str, str] = {}
            for item in metadata:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    result[str(item[0]).lower()] = str(item[1])
            return result

        return {}

    def create_metadata(
        self,
        sender_id: str,
        receiver_id: str,
        task_id: Optional[str] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> List[Tuple[str, str]]:
        """Create gRPC metadata for an A2A message.

        Args:
            sender_id: Sender agent identifier.
            receiver_id: Receiver agent identifier.
            task_id: Optional task identifier.
            extra: Additional metadata entries.

        Returns:
            List of (key, value) tuples for gRPC metadata.
        """
        metadata: List[Tuple[str, str]] = [
            (self.SENDER_KEY, sender_id),
            (self.RECEIVER_KEY, receiver_id),
        ]

        if task_id:
            metadata.append((self.TASK_KEY, task_id))

        if extra:
            for key, value in extra.items():
                metadata.append((key, value))

        return metadata

    @property
    def message_count(self) -> int:
        """Total messages processed."""
        return self._message_count
