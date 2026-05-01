"""
A2A 0.3.0 JSON-RPC Adapter (Section 10.4).

Extracts sender and receiver identifiers from A2A JSON-RPC messages
following the Agent-to-Agent protocol specification v0.3.0.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from .generic import NormalizedMessage

logger = logging.getLogger("a2astc.adapters.a2a_jsonrpc")


class A2AJsonRpcAdapter:
    """Adapter for A2A 0.3.0 over JSON-RPC transport.

    Parses JSON-RPC request/response envelopes and extracts agent
    identifiers from the A2A protocol fields.

    A2A JSON-RPC message format:
    {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "id": "...",
        "params": {
            "id": "task-id",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "..."}]
            },
            "metadata": {
                "sender_agent_id": "agent-a",
                "receiver_agent_id": "agent-b"
            }
        }
    }
    """

    def __init__(self) -> None:
        self._message_count: int = 0

    def normalize(
        self,
        raw_message: str | bytes | Dict[str, Any],
        fallback_sender: str = "unknown",
        fallback_receiver: str = "unknown",
    ) -> NormalizedMessage:
        """Normalize an A2A JSON-RPC message.

        Args:
            raw_message: The raw JSON-RPC message (string, bytes, or dict).
            fallback_sender: Sender ID to use if not found in message.
            fallback_receiver: Receiver ID to use if not found in message.

        Returns:
            NormalizedMessage with extracted identifiers.
        """
        self._message_count += 1

        if isinstance(raw_message, (str, bytes)):
            try:
                data = json.loads(raw_message)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning("Failed to parse JSON-RPC message")
                return NormalizedMessage(
                    sender_id=fallback_sender,
                    receiver_id=fallback_receiver,
                    payload=str(raw_message),
                    headers={"x-a2astc-parse-error": "true"},
                    raw=raw_message,
                )
        else:
            data = raw_message

        # Extract identifiers from A2A structure
        sender_id, receiver_id = self._extract_identifiers(
            data, fallback_sender, fallback_receiver
        )

        # Extract payload
        payload = self._extract_payload(data)

        # Build headers from metadata
        headers = self._extract_headers(data)

        return NormalizedMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            payload=payload,
            headers=headers,
            raw=data,
        )

    def _extract_identifiers(
        self,
        data: Dict[str, Any],
        fallback_sender: str,
        fallback_receiver: str,
    ) -> Tuple[str, str]:
        """Extract sender and receiver from A2A JSON-RPC structure."""
        params = data.get("params", {})

        # Primary: check metadata block
        metadata = params.get("metadata", {})
        sender = metadata.get("sender_agent_id", "")
        receiver = metadata.get("receiver_agent_id", "")

        # Fallback: check top-level params
        if not sender:
            sender = params.get("sender_id", params.get("from", ""))
        if not receiver:
            receiver = params.get("receiver_id", params.get("to", ""))

        # Fallback: check message.metadata
        message = params.get("message", {})
        if isinstance(message, dict):
            msg_meta = message.get("metadata", {})
            if not sender:
                sender = msg_meta.get("sender_agent_id", "")
            if not receiver:
                receiver = msg_meta.get("receiver_agent_id", "")

        return sender or fallback_sender, receiver or fallback_receiver

    def _extract_payload(self, data: Dict[str, Any]) -> str:
        """Extract message payload from A2A structure."""
        params = data.get("params", {})
        message = params.get("message", {})

        if isinstance(message, dict):
            parts = message.get("parts", [])
            text_parts = []
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            if text_parts:
                return " ".join(text_parts)

            # Fallback: stringify the message
            return json.dumps(message)

        return str(message)

    def _extract_headers(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Extract headers from JSON-RPC metadata."""
        headers: Dict[str, str] = {}

        # JSON-RPC method
        method = data.get("method", "")
        if method:
            headers["x-a2a-method"] = method

        # JSON-RPC id
        rpc_id = data.get("id", "")
        if rpc_id:
            headers["x-a2a-rpc-id"] = str(rpc_id)

        # Task ID
        params = data.get("params", {})
        task_id = params.get("id", "")
        if task_id:
            headers["x-a2a-task-id"] = str(task_id)

        # A2A protocol version
        headers["x-a2a-protocol"] = "a2a-0.3.0"
        headers["x-a2a-transport"] = "json-rpc"

        return headers

    def wrap_response(
        self,
        rpc_id: str,
        result: Dict[str, Any],
        a2astc_verdict: str = "ALLOW",
    ) -> Dict[str, Any]:
        """Wrap a gate result as A2A JSON-RPC response metadata.

        Args:
            rpc_id: The JSON-RPC request ID.
            result: The result to include.
            a2astc_verdict: The A2ASTC gate verdict.

        Returns:
            JSON-RPC response envelope with A2ASTC metadata.
        """
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                **result,
                "metadata": {
                    "a2astc_verdict": a2astc_verdict,
                    "a2astc_version": "0.1.0",
                },
            },
        }

    @property
    def message_count(self) -> int:
        """Total messages processed."""
        return self._message_count
