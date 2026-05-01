# A2ASTC Integration Guide

## Overview

A2ASTC integrates as middleware into any agent-to-agent communication system.
The `TeamComplianceGate` is the primary integration point -- it wraps your
message dispatch path and evaluates each message before delivery.

## Quick Start

```python
from thinkneo_a2astc import TeamComplianceGate

gate = TeamComplianceGate()
```

That is the minimum viable integration. The gate will use default configuration.

## Integration Patterns

### Pattern 1: A2A JSON-RPC

For systems using the A2A 0.3.0 JSON-RPC transport:

```python
from thinkneo_a2astc import TeamComplianceGate
from thinkneo_a2astc.adapters import A2AJsonRpcAdapter

gate = TeamComplianceGate()
adapter = A2AJsonRpcAdapter()

async def handle_jsonrpc(raw_message: str) -> dict:
    # Normalize the A2A message
    normalized = adapter.normalize(raw_message)

    # Evaluate through the compliance gate
    result = gate.evaluate(
        sender_id=normalized.sender_id,
        receiver_id=normalized.receiver_id,
        payload=normalized.payload,
    )

    if result.verdict.value == "ALLOW":
        # Proceed with delivery
        delivery = await deliver_message(raw_message)
        return adapter.wrap_response(
            normalized.headers.get("x-a2a-rpc-id", ""),
            delivery,
            "ALLOW",
        )
    else:
        # Block or modify delivery based on verdict
        return adapter.wrap_response(
            normalized.headers.get("x-a2a-rpc-id", ""),
            {"error": f"Blocked: {result.verdict.value}"},
            result.verdict.value,
        )
```

### Pattern 2: A2A gRPC

For gRPC-based A2A systems:

```python
from thinkneo_a2astc import TeamComplianceGate
from thinkneo_a2astc.adapters import A2AGrpcAdapter

gate = TeamComplianceGate()
adapter = A2AGrpcAdapter()

class A2AServiceInterceptor:
    async def intercept(self, request, metadata, handler):
        normalized = adapter.normalize(
            payload=request.SerializeToString(),
            metadata=metadata,
        )

        result = gate.evaluate(
            sender_id=normalized.sender_id,
            receiver_id=normalized.receiver_id,
            payload=normalized.payload,
        )

        if result.verdict.value in ("ALLOW", "WARN"):
            return await handler(request, metadata)
        else:
            raise PermissionError(f"A2ASTC: {result.verdict.value}")
```

### Pattern 3: MCP-Bridged A2A

For agents communicating via MCP tool calls:

```python
from thinkneo_a2astc import TeamComplianceGate
from thinkneo_a2astc.adapters import MCPBridgeAdapter

gate = TeamComplianceGate()
adapter = MCPBridgeAdapter()

async def handle_tool_call(tool_call: dict, context: dict) -> dict:
    if adapter.is_a2a_tool_call(tool_call.get("tool", "")):
        normalized = adapter.normalize(tool_call, context)

        result = gate.evaluate(
            sender_id=normalized.sender_id,
            receiver_id=normalized.receiver_id,
            payload=normalized.payload,
        )

        if result.verdict.value != "ALLOW":
            return adapter.wrap_tool_result(
                {"error": f"Blocked by A2ASTC: {result.verdict.value}"},
                result.verdict.value,
            )

    # Proceed with normal tool execution
    tool_result = await execute_tool(tool_call)
    return adapter.wrap_tool_result(tool_result, "ALLOW")
```

### Pattern 4: Generic / Direct

For custom systems or in-process agent communication:

```python
from thinkneo_a2astc import TeamComplianceGate

gate = TeamComplianceGate()

# Register agents with their capabilities
gate.register_agent("agent-researcher", capabilities={"read-untrusted", "summarize"})
gate.register_agent("agent-writer", capabilities={"write-trusted", "translate"})

# Evaluate each message
result = gate.evaluate(
    sender_id="agent-researcher",
    receiver_id="agent-writer",
    payload="Here is the research data...",
)

if result.verdict.value == "ALLOW":
    deliver(message)
elif result.verdict.value == "WARN":
    deliver(message, warning=result.reasons)
else:
    block(message, reason=result.verdict.value)
```

## Async Middleware Hooks

For frameworks that support async middleware:

```python
gate = TeamComplianceGate()

# Add as middleware to your A2A server
server.add_pre_dispatch(gate.on_message_pre_dispatch)
server.add_post_dispatch(gate.on_message_post_dispatch)
server.add_disconnect_handler(gate.on_agent_disconnect)
server.add_shutdown_handler(gate.on_shutdown)
```

## Configuration

See `policy-authoring.md` for custom policies and `operations-runbook.md`
for deployment configuration.

## Agent Registration

For best results, register agents with their capabilities before they
begin communicating:

```python
gate.register_agent(
    agent_id="my-agent",
    provider="anthropic",
    model_class="claude-3",
    capabilities={"read-untrusted", "code-exec"},
)
```

This allows the gate to compute accurate safety classifications
from the moment teams form.
