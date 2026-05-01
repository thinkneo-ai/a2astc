"""
Protocol Adapters (Section 10.4).

Adapters normalize different transport protocols into the standard
(sender_id, receiver_id, payload, headers) tuple format used by the gate.
"""

from .generic import GenericAdapter
from .a2a_jsonrpc import A2AJsonRpcAdapter
from .a2a_grpc import A2AGrpcAdapter
from .mcp_bridge import MCPBridgeAdapter

__all__ = [
    "GenericAdapter",
    "A2AJsonRpcAdapter",
    "A2AGrpcAdapter",
    "MCPBridgeAdapter",
]
