"""
MCP-Bridged A2A Adapter (Section 10.4).

Extracts agent identifiers from MCP tool call context when
A2A messages are bridged through Model Context Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .generic import NormalizedMessage

logger = logging.getLogger("a2astc.adapters.mcp_bridge")


class MCPBridgeAdapter:
    """Adapter for A2A messages bridged through MCP.

    When agents communicate via MCP tool calls, the A2A semantics
    are carried within the tool call parameters. This adapter
    extracts the underlying A2A identifiers.

    Expected MCP tool call structure:
    {
        "tool": "a2a_send" | "a2a_delegate" | ...,
        "arguments": {
            "target_agent": "receiver-id",
            "message": "...",
            "task_id": "...",
            ...
        },
        "context": {
            "caller_agent_id": "sender-id",
            "session_id": "...",
            ...
        }
    }
    """

    # Known MCP tool names that carry A2A semantics
    A2A_TOOL_NAMES = frozenset({
        "a2a_send",
        "a2a_delegate",
        "a2a_query",
        "a2a_respond",
        "agent_send",
        "agent_delegate",
        "send_to_agent",
        "delegate_task",
    })

    def __init__(
        self,
        additional_tool_names: Optional[set] = None,
    ) -> None:
        self._message_count: int = 0
        self._tool_names = set(self.A2A_TOOL_NAMES)
        if additional_tool_names:
            self._tool_names.update(additional_tool_names)

    def is_a2a_tool_call(self, tool_name: str) -> bool:
        """Check if an MCP tool call carries A2A semantics."""
        return tool_name.lower() in self._tool_names

    def normalize(
        self,
        tool_call: Dict[str, Any],
        caller_context: Optional[Dict[str, Any]] = None,
        fallback_sender: str = "unknown",
        fallback_receiver: str = "unknown",
    ) -> NormalizedMessage:
        """Normalize an MCP-bridged A2A tool call.

        Args:
            tool_call: The MCP tool call dict with 'tool', 'arguments'.
            caller_context: MCP caller context with agent identity.
            fallback_sender: Default sender if not found.
            fallback_receiver: Default receiver if not found.

        Returns:
            NormalizedMessage with extracted identifiers.
        """
        self._message_count += 1

        arguments = tool_call.get("arguments", {})
        context = tool_call.get("context", caller_context or {})

        # Extract sender from MCP context
        sender = (
            context.get("caller_agent_id")
            or context.get("agent_id")
            or context.get("sender_id")
            or arguments.get("sender_id")
            or fallback_sender
        )

        # Extract receiver from tool arguments
        receiver = (
            arguments.get("target_agent")
            or arguments.get("target_agent_id")
            or arguments.get("receiver_id")
            or arguments.get("to")
            or arguments.get("agent_id")
            or fallback_receiver
        )

        # Extract payload
        payload = (
            arguments.get("message")
            or arguments.get("content")
            or arguments.get("payload")
            or arguments.get("text")
            or json.dumps(arguments)
        )
        if not isinstance(payload, str):
            payload = json.dumps(payload)

        # Build headers
        headers: Dict[str, str] = {
            "x-a2a-protocol": "a2a-0.3.0",
            "x-a2a-transport": "mcp-bridge",
            "x-mcp-tool": str(tool_call.get("tool", "")),
        }

        session_id = context.get("session_id")
        if session_id:
            headers["x-mcp-session-id"] = str(session_id)

        task_id = arguments.get("task_id")
        if task_id:
            headers["x-a2a-task-id"] = str(task_id)

        return NormalizedMessage(
            sender_id=sender,
            receiver_id=receiver,
            payload=payload,
            headers=headers,
            raw=tool_call,
        )

    def wrap_tool_result(
        self,
        result: Dict[str, Any],
        a2astc_verdict: str = "ALLOW",
        warnings: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Wrap a gate result as MCP tool result metadata.

        Args:
            result: The tool result to wrap.
            a2astc_verdict: The A2ASTC gate verdict.
            warnings: Any warning messages.

        Returns:
            MCP tool result with A2ASTC metadata.
        """
        wrapped = dict(result)
        wrapped["_a2astc"] = {
            "verdict": a2astc_verdict,
            "version": "0.1.0",
        }
        if warnings:
            wrapped["_a2astc"]["warnings"] = warnings
        return wrapped

    @property
    def message_count(self) -> int:
        """Total messages processed."""
        return self._message_count
