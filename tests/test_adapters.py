"""Tests for Protocol Adapters (Section 10.4)."""

import json
import pytest
from thinkneo_a2astc.adapters.generic import GenericAdapter, NormalizedMessage
from thinkneo_a2astc.adapters.a2a_jsonrpc import A2AJsonRpcAdapter
from thinkneo_a2astc.adapters.a2a_grpc import A2AGrpcAdapter
from thinkneo_a2astc.adapters.mcp_bridge import MCPBridgeAdapter


class TestGenericAdapter:
    """Tests for the generic adapter."""

    def test_normalize_strings(self):
        """Should normalize string inputs."""
        adapter = GenericAdapter()
        msg = adapter.normalize("agent-a", "agent-b", "hello world")
        assert msg.sender_id == "agent-a"
        assert msg.receiver_id == "agent-b"
        assert msg.payload == "hello world"

    def test_normalize_bytes(self):
        """Should handle bytes payload."""
        adapter = GenericAdapter()
        msg = adapter.normalize("a", "b", b"binary data")
        assert msg.payload == "binary data"

    def test_to_tuple(self):
        """Should convert to standard tuple."""
        adapter = GenericAdapter()
        msg = adapter.normalize("a", "b", "payload", {"key": "val"})
        t = msg.to_tuple()
        assert t == ("a", "b", "payload", {"key": "val"})

    def test_from_dict(self):
        """Should create from dictionary."""
        adapter = GenericAdapter()
        msg = adapter.from_dict({
            "sender_id": "x",
            "receiver_id": "y",
            "payload": "test",
        })
        assert msg.sender_id == "x"
        assert msg.receiver_id == "y"

    def test_message_count(self):
        """Should track message count."""
        adapter = GenericAdapter()
        adapter.normalize("a", "b", "1")
        adapter.normalize("a", "b", "2")
        assert adapter.message_count == 2


class TestA2AJsonRpcAdapter:
    """Tests for A2A JSON-RPC adapter."""

    def test_extract_from_metadata(self):
        """Should extract IDs from A2A metadata."""
        adapter = A2AJsonRpcAdapter()
        msg = adapter.normalize({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": "req-1",
            "params": {
                "id": "task-1",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Hello agent B"}],
                },
                "metadata": {
                    "sender_agent_id": "agent-a",
                    "receiver_agent_id": "agent-b",
                },
            },
        })
        assert msg.sender_id == "agent-a"
        assert msg.receiver_id == "agent-b"
        assert "Hello agent B" in msg.payload

    def test_extract_payload_text(self):
        """Should extract text from message parts."""
        adapter = A2AJsonRpcAdapter()
        msg = adapter.normalize({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "message": {
                    "parts": [
                        {"type": "text", "text": "Part 1"},
                        {"type": "text", "text": "Part 2"},
                    ],
                },
                "metadata": {"sender_agent_id": "a", "receiver_agent_id": "b"},
            },
        })
        assert "Part 1" in msg.payload
        assert "Part 2" in msg.payload

    def test_fallback_ids(self):
        """Should use fallback when IDs not found."""
        adapter = A2AJsonRpcAdapter()
        msg = adapter.normalize({"jsonrpc": "2.0", "params": {}})
        assert msg.sender_id == "unknown"
        assert msg.receiver_id == "unknown"

    def test_parse_json_string(self):
        """Should parse JSON string."""
        adapter = A2AJsonRpcAdapter()
        raw = json.dumps({
            "jsonrpc": "2.0",
            "params": {
                "metadata": {"sender_agent_id": "s", "receiver_agent_id": "r"},
                "message": {"parts": [{"type": "text", "text": "hi"}]},
            },
        })
        msg = adapter.normalize(raw)
        assert msg.sender_id == "s"

    def test_headers_include_protocol(self):
        """Headers should include protocol info."""
        adapter = A2AJsonRpcAdapter()
        msg = adapter.normalize({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {"metadata": {"sender_agent_id": "a", "receiver_agent_id": "b"}},
        })
        assert msg.headers["x-a2a-protocol"] == "a2a-0.3.0"
        assert msg.headers["x-a2a-transport"] == "json-rpc"

    def test_wrap_response(self):
        """Should wrap response with A2ASTC metadata."""
        adapter = A2AJsonRpcAdapter()
        resp = adapter.wrap_response("req-1", {"status": "ok"}, "ALLOW")
        assert resp["jsonrpc"] == "2.0"
        assert resp["result"]["metadata"]["a2astc_verdict"] == "ALLOW"


class TestA2AGrpcAdapter:
    """Tests for A2A gRPC adapter."""

    def test_extract_from_dict_metadata(self):
        """Should extract from dict metadata."""
        adapter = A2AGrpcAdapter()
        msg = adapter.normalize(
            "test payload",
            {"x-a2a-sender-agent-id": "s", "x-a2a-receiver-agent-id": "r"},
        )
        assert msg.sender_id == "s"
        assert msg.receiver_id == "r"

    def test_extract_from_tuple_metadata(self):
        """Should extract from list-of-tuples metadata."""
        adapter = A2AGrpcAdapter()
        msg = adapter.normalize(
            "payload",
            [("x-a2a-sender-agent-id", "sender"), ("x-a2a-receiver-agent-id", "recv")],
        )
        assert msg.sender_id == "sender"
        assert msg.receiver_id == "recv"

    def test_create_metadata(self):
        """Should create gRPC metadata tuples."""
        adapter = A2AGrpcAdapter()
        meta = adapter.create_metadata("s", "r", "task-1")
        meta_dict = dict(meta)
        assert meta_dict["x-a2a-sender-agent-id"] == "s"
        assert meta_dict["x-a2a-receiver-agent-id"] == "r"


class TestMCPBridgeAdapter:
    """Tests for MCP bridge adapter."""

    def test_extract_from_tool_call(self):
        """Should extract IDs from MCP tool call."""
        adapter = MCPBridgeAdapter()
        msg = adapter.normalize(
            {
                "tool": "a2a_send",
                "arguments": {
                    "target_agent": "agent-b",
                    "message": "Hello from A",
                },
                "context": {
                    "caller_agent_id": "agent-a",
                },
            }
        )
        assert msg.sender_id == "agent-a"
        assert msg.receiver_id == "agent-b"
        assert "Hello from A" in msg.payload

    def test_is_a2a_tool_call(self):
        """Should identify A2A tool calls."""
        adapter = MCPBridgeAdapter()
        assert adapter.is_a2a_tool_call("a2a_send") is True
        assert adapter.is_a2a_tool_call("regular_tool") is False

    def test_wrap_tool_result(self):
        """Should wrap result with A2ASTC metadata."""
        adapter = MCPBridgeAdapter()
        result = adapter.wrap_tool_result({"data": "test"}, "WARN", ["high risk"])
        assert result["_a2astc"]["verdict"] == "WARN"
        assert "high risk" in result["_a2astc"]["warnings"]

    def test_custom_tool_names(self):
        """Should support custom tool names."""
        adapter = MCPBridgeAdapter(additional_tool_names={"my_custom_send"})
        assert adapter.is_a2a_tool_call("my_custom_send") is True
