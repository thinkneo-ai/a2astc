# A2ASTC -- Agent to Agent Software Team Compliance

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://pypi.org/project/thinkneo-a2astc/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-200%2B-brightgreen.svg)](tests/)
[![Conformance](https://img.shields.io/badge/TCK-15%20fixtures-orange.svg)](conformance/)

**Runtime compliance layer for multi-agent AI systems.**

A2ASTC treats the emergent team formed when agents exchange A2A messages as a
first-class governed entity. It detects team formation, audits emergent
behavior, enforces compliance verdicts, and maintains a tamper-evident
audit trail.

> Publisher: **ThinkNEO AI Technology Company Limited** (Hong Kong)
> Specification: [SPEC.md](SPEC.md) | Website: [a2astc.space](https://a2astc.space)

---

## The Compound-System Gap

Individual AI agents are evaluated in isolation: each has its own safety
classification, rate limits, and capability boundaries. But when agents
collaborate -- exchanging messages, delegating tasks, sharing results --
the **team** they form can exceed the safety properties of any individual
member.

A2ASTC closes this gap by monitoring agent-to-agent communication in
real-time and treating the emergent team as a governed entity with its own:

- **Manifest** (members, capabilities, safety classification)
- **Risk score** (composite of 5 signal families)
- **Compliance verdicts** (ALLOW / WARN / THROTTLE / ISOLATE / TERMINATE)
- **Audit trail** (hash-chained, tamper-evident)

---

## Quick Start

```python
from thinkneo_a2astc import TeamComplianceGate

gate = TeamComplianceGate()
result = gate.evaluate("agent-a", "agent-b", "message payload")
print(result.verdict)  # ALLOW | WARN | THROTTLE | ISOLATE | TERMINATE
```

That's it. Two lines to add runtime compliance to any multi-agent system.

---

## Architecture

```
  Agent A          Agent B          Agent C
     |                |                |
     v                v                v
+----------------------------------------------------+
|              TeamComplianceGate                     |
|                                                    |
|  +------------+  +----------+  +----------------+  |
|  | Detector   |  | Manifest |  | Audit Signals  |  |
|  | (Sec. 4)   |  | (Sec. 5) |  | (Sec. 6)       |  |
|  +-----+------+  +----+-----+  +---+---+---+----+  |
|        |              |            |   |   |   |    |
|        v              v            v   v   v   v    |
|  +------------+  Topology  Semantic  Privilege      |
|  | Gate       |  SideChannel  Cascade               |
|  | (Sec. 7)   |                                    |
|  +-----+------+                                    |
|        |                                           |
|        v                                           |
|  +----------------+  +-------------------+          |
|  | Intervention   |  | Audit Trail       |          |
|  | (Sec. 8)       |  | (Sec. 9)          |          |
|  +----------------+  +-------------------+          |
+----------------------------------------------------+
```

## Signal Families

| # | Signal | Detects |
|---|--------|---------|
| 1 | **Topology** | Star/mesh patterns, sub-coalitions, degree skew |
| 2 | **Semantic** | Vocabulary convergence, objective alignment |
| 3 | **Privilege** | Capability laundering, boundary violations |
| 4 | **Side-Channel** | Timing patterns, length encoding, ordering |
| 5 | **Cascade** | Multi-hop deception, prompt injection chains |

Composite risk: `R_team = 1 - PROD(1 - w_i * s_i)` (default weights: 0.2 each)

## Verdict Bands

| Score Range | Verdict | Action |
|-------------|---------|--------|
| [0.00, 0.40) | ALLOW | Deliver message normally |
| [0.40, 0.65) | WARN | Deliver with warning header |
| [0.65, 0.80) | THROTTLE | Rate-limit via token bucket |
| [0.80, 0.92) | ISOLATE | Block specific edge |
| [0.92, 1.00] | TERMINATE | Block all team edges (irreversible) |

## Conformance Test Kit

15 adversarial fixtures validate detection of:

| ID | Fixture | Signal |
|----|---------|--------|
| TCK-001 | Capability Laundering | privilege |
| TCK-002 | Emergent Collusion | semantic |
| TCK-003 | Deceptive Cascade | cascade |
| TCK-004 | Side-Channel Timing | sidechannel |
| TCK-005 | Side-Channel Length | sidechannel |
| TCK-006 | Steganography Metadata | sidechannel |
| TCK-007 | Privilege Aggregation | privilege |
| TCK-008 | Identity Multiplication | topology |
| TCK-009 | Prompt Injection Cascade | cascade |
| TCK-010 | Coalition Against Third | topology |
| TCK-011 | Convergent Vocabulary | semantic |
| TCK-012 | Throttle Evasion | topology |
| TCK-013 | Isolation Evasion | topology |
| TCK-014 | Manifest Desync | topology |
| TCK-015 | Trail Tamper | cascade |

## Documentation

- [Integration Guide](docs/integration-guide.md)
- [Policy Authoring](docs/policy-authoring.md)
- [Operations Runbook](docs/operations-runbook.md)
- [Threat Model](docs/threat-model.md)
- [Full Specification](SPEC.md)

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run benchmarks
pytest benchmarks/ -v --benchmark-only

# Run conformance
python -m conformance.runner
```

## License

Apache-2.0. See [LICENSE](LICENSE).

## Publisher

ThinkNEO AI Technology Company Limited (Hong Kong)
