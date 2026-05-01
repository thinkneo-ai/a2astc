# A2ASTC -- Agent to Agent Software Team Compliance

**Specification version:** 0.1.0
**Status:** Standalone production specification
**Publisher:** ThinkNEO AI Technology Company Limited (Hong Kong)
**Reference implementation:** thinkneo-ai/a2astc
**PyPI package:** thinkneo-a2astc
**Date:** 2026-05-01
**License:** Apache-2.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope and Motivation](#2-scope-and-motivation)
3. [Terminology](#3-terminology)
4. [Architecture Overview](#4-architecture-overview)
5. [Team Detection](#5-team-detection)
6. [Team Manifest](#6-team-manifest)
7. [Emergent Behavior Audit](#7-emergent-behavior-audit)
8. [Team Compliance Gate](#8-team-compliance-gate)
9. [Intervention Layer](#9-intervention-layer)
10. [Team Audit Trail](#10-team-audit-trail)
11. [Integration Contract](#11-integration-contract)
12. [Conformance Levels](#12-conformance-levels)
13. [Adversarial Fixtures](#13-adversarial-fixtures)
14. [Operational Guarantees](#14-operational-guarantees)
15. [Schemas](#15-schemas)
16. [Security Considerations](#16-security-considerations)
17. [Versioning](#17-versioning)
18. [Repository Layout](#18-repository-layout)
19. [Commercial Positioning](#19-commercial-positioning)
20. [Acknowledgments and Change Log](#20-acknowledgments-and-change-log)

---

## 1. Executive Summary

A2ASTC (Agent to Agent Software Team Compliance) is a runtime compliance layer for multi-agent AI systems. It addresses a critical gap in current AI safety infrastructure: **individual agents are evaluated in isolation, but the emergent team they form when collaborating can exceed the safety properties of any individual member.**

A2ASTC treats the team formed by communicating agents as a first-class governed entity. It:

- **Detects** team formation from bidirectional communication patterns
- **Manifests** the team with versioned membership, capabilities, and safety classification
- **Audits** emergent behavior across five orthogonal signal families
- **Gates** every message with a synchronous compliance verdict
- **Intervenes** with graduated responses (warn, throttle, isolate, terminate)
- **Trails** every event in a tamper-evident hash-chained audit log

The specification is transport-agnostic and works with A2A JSON-RPC, A2A gRPC, MCP-bridged A2A, and any generic tuple-based message passing.

---

## 2. Scope and Motivation

### 2.1 The Compound-System Gap

Modern AI deployments increasingly involve multiple agents collaborating on tasks. Each agent may be individually safe -- passing evaluations, respecting rate limits, operating within declared capabilities. However, when agents form an ad-hoc team:

- **Capabilities aggregate.** Agent A has `read-untrusted`, Agent B has `write-trusted`. Together, they can read untrusted data and write it to trusted stores -- a capability neither was individually authorized to perform.
- **Behaviors emerge.** Agents may develop shared vocabulary, converge on objectives, or coordinate in ways not anticipated by their individual safety assessments.
- **Accountability fragments.** No single agent is responsible for team-level outcomes. Audit trails track individual actions but miss the team dynamics.

### 2.2 Scope

A2ASTC covers:

- Runtime detection and governance of agent teams
- Compliance evaluation of inter-agent messages
- Graduated intervention mechanisms
- Tamper-evident audit trails

A2ASTC does NOT cover:

- Individual agent safety evaluation (that is the provider's responsibility)
- Training-time alignment
- Human-in-the-loop approval workflows (though it can trigger them)
- Network-level security (TLS, authentication, authorization)

### 2.3 Design Principles

1. **Zero-trust team formation.** Every team starts untrusted and must continuously earn compliance.
2. **Graduated response.** The system prefers reversible interventions over termination.
3. **Composable signals.** Five orthogonal signal families combine into a single risk score.
4. **Deterministic gate.** Given the same inputs, the gate always produces the same verdict.
5. **Tamper-evident trail.** The audit log is hash-chained and append-only.
6. **Transport-agnostic.** Works with any message-passing protocol via adapters.

---

## 3. Terminology

| Term | Definition |
|------|-----------|
| **Agent** | An autonomous AI system that sends and receives messages. |
| **Edge** | A directed communication event from one agent to another. |
| **Pair** | A bidirectional communication relationship between two agents (A to B and B to A both observed). |
| **Team** | The emergent entity formed when agents communicate bidirectionally. Minimum 2 members. |
| **Manifest** | A versioned document describing a team's membership, capabilities, and safety classification. |
| **Signal** | A metric produced by one of the five audit signal families. |
| **R_team** | The composite team risk score, computed from weighted signals. Range [0, 1]. |
| **Verdict** | The gate's decision on a message: ALLOW, WARN, THROTTLE, ISOLATE, or TERMINATE. |
| **Intervention** | An enforcement action applied to an edge or team based on the verdict. |
| **Trail** | The append-only, hash-chained audit log. |
| **Capability** | A declared ability of an agent (e.g., `code-exec`, `net-egress`, `read-untrusted`). |
| **Safety Class** | Aggregate classification of a team based on its combined capabilities: STANDARD, RESTRICTED, HIGH_RISK. |
| **Escalation** | When aggregate capabilities exceed thresholds that individual capabilities do not. |
| **Sliding Window** | The time window within which edges are considered active for team detection. |
| **Token Bucket** | Rate limiting mechanism used for THROTTLE interventions. |
| **Cooldown** | The minimum time before a reversible intervention can be released. |
| **TCK** | Team Compliance Kit -- the conformance test suite. |

---

## 4. Architecture Overview

```
  Agent A          Agent B          Agent C
     |                |                |
     +---message----->+                |
     +<--message------+                |
     |                +---message----->+
     |                +<--message------+
     v                v                v
+----------------------------------------------------+
|              TeamComplianceGate                     |
|                                                    |
|  +-----------+  +-----------+  +-----------------+ |
|  | Detector  |  | Manifest  |  | Audit Signals   | |
|  | (Sec 5)   |  | (Sec 6)   |  | (Sec 7)         | |
|  +-----+-----+  +-----+-----+  +--+--+--+--+--+ | |
|        |              |           |  |  |  |  |   | |
|  +-----v--------------v-----------v--v--v--v--v-+ | |
|  |          Gate Evaluation (Sec 8)              | | |
|  +-----+-----------------------------------------+ |
|        |                                           |
|  +-----v-----------+  +--------------------------+ |
|  | Intervention     |  | Audit Trail             | |
|  | (Sec 9)          |  | (Sec 10)                | |
|  +------------------+  +--------------------------+ |
+----------------------------------------------------+
```

The gate is deployed as synchronous middleware in the message delivery path. Every message passes through the gate before delivery. The gate is the integration point; all other components are internal.

---

## 5. Team Detection

### 5.1 Edge Observation

The detector observes directed edges as tuples: `(sender_id, receiver_id, timestamp)`. Edges are stored in a sliding window of configurable duration (default: 600 seconds).

### 5.2 Pair Formation

A **bidirectional pair** `{A, B}` is formed when both `A -> B` and `B -> A` edges are observed within the sliding window. Self-loops (`A -> A`) are ignored.

### 5.3 Team Formation

When a bidirectional pair `{A, B}` is detected and neither A nor B belongs to an existing team, a new team is formed with a unique identifier (UUIDv7 preferred, UUIDv4 fallback).

### 5.4 Team Growth

When a new bidirectional pair `{B, C}` is detected and B already belongs to team T, agent C is added to team T. The pair is recorded in the team's pair set.

### 5.5 Team Merging

When a new bidirectional pair `{A, C}` is detected where A belongs to team T1 and C belongs to team T2 (and T1 != T2), the teams are merged. T1 absorbs T2's members and pairs. T2 is marked as dissolved.

### 5.6 Team Dissolution

A team is dissolved when its membership drops below the minimum team size (default: 2). This occurs when:

- An agent is explicitly removed (disconnect, timeout)
- Pairs expire outside the sliding window and remaining members are insufficient

### 5.7 Data Structures

```
pending_edges: List[Edge]              # All edges in the sliding window
active_pairs: Set[FrozenSet[str]]      # Currently active bidirectional pairs
teams: Dict[str, Team]                 # All teams, keyed by team_id
direction_map: Dict[(str,str), float]  # Last timestamp per directed edge
```

---

## 6. Team Manifest

### 6.1 Manifest Structure

Each team has a versioned manifest containing:

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | string | Unique team identifier |
| `members` | Map[str, MemberRecord] | Agent ID to member record |
| `state` | TeamState | Current lifecycle state |
| `version` | int | Monotonically increasing version counter |
| `created_at` | float | Team creation timestamp |
| `updated_at` | float | Last modification timestamp |
| `aggregate_capabilities` | Set[str] | Union of all member capabilities |
| `safety_class` | SafetyClass | Aggregate safety classification |
| `metadata` | Dict | Optional metadata |

### 6.2 Member Record

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Unique agent identifier |
| `provider` | string | Agent provider (e.g., "openai", "anthropic") |
| `model_class` | string | Model classification |
| `capabilities` | Set[str] | Declared capabilities |
| `joined_ts` | float | When the agent joined the team |
| `role_inferred` | string | Inferred role (peer, coordinator, worker, observer) |

### 6.3 Team States

| State | Description |
|-------|-------------|
| FORMING | Team detected but below minimum size |
| ACTIVE | Team operational with sufficient members |
| THROTTLED | Team under throttle intervention |
| ISOLATED | One or more edges isolated |
| TERMINATED | All edges blocked (irreversible for team lifetime) |
| DISSOLVED | Team disbanded (membership below minimum or explicit) |

### 6.4 Capability Aggregation

The aggregate capabilities are the set union of all member capabilities:

```
aggregate_capabilities = UNION(member.capabilities for member in team.members)
```

### 6.5 Escalation Thresholds

| Capability Pair | Classification |
|----------------|---------------|
| `read-untrusted` + `write-trusted` | RESTRICTED |
| `code-exec` + `net-egress` | RESTRICTED |
| `memory-write` + `identity-assumption` | RESTRICTED |
| Any 3 of: `read-untrusted`, `code-exec`, `memory-write`, `identity-assumption` | HIGH_RISK |
| All 4 of the above | HIGH_RISK |

### 6.6 Version Monotonicity

The manifest version counter is incremented on every modification (member add/remove, state change, capability update). It never decreases.

---

## 7. Emergent Behavior Audit

Five orthogonal signal families monitor the team for emergent behaviors that may indicate risk. Each produces a risk score in the range [0, 1].

### 7.1 Topology Signals

Analyzes the communication graph structure:

| Metric | Description |
|--------|-------------|
| Edge density | Ratio of actual to maximum possible edges |
| Degree distribution | In/out-degree skew across members |
| Clustering coefficient | Average local clustering |
| Topology classification | Star, ring, mesh, hierarchical, unclassified |
| Sub-coalition detection | Densely connected subgroups within the team |

**High risk indicators:** Star topology (central control), very high density with high clustering, multiple sub-coalitions, extreme degree skew.

### 7.2 Semantic Signals

Tracks message content convergence:

| Metric | Description |
|--------|-------------|
| Pairwise similarity | Cosine similarity of character n-gram vectors |
| Vocabulary overlap | Jaccard similarity of agent vocabularies |
| Convergence trend | Linear regression slope of similarity over time |
| Specialized terms | High TF-IDF terms shared by multiple team members |

**High risk indicators:** High pairwise similarity, increasing convergence trend, development of specialized vocabulary not present in initial communications.

### 7.3 Privilege Signals

Monitors capability invocations:

| Metric | Description |
|--------|-------------|
| Laundering chains | Agent A's capability output flows to Agent B who lacks that capability |
| Privilege concentration | Gini coefficient of capability usage |
| Boundary violations | Invocations of undeclared capabilities |
| Capability breadth | Unique capabilities used relative to team size |

**High risk indicators:** Any laundering chain, high privilege concentration, boundary violations.

### 7.4 Side-Channel Signals

Detects covert communication patterns:

| Metric | Description |
|--------|-------------|
| Timing regularity | Coefficient of variation of inter-message delays |
| Length patterns | Parity bias, modular encoding, length clustering |
| Ordering patterns | Periodic sender sequences, strict request-response pairing |

**High risk indicators:** Very regular timing (CV < 0.05), strong parity bias (> 0.7), periodic sender patterns.

### 7.5 Cascade Signals

Detects multi-hop deceptive chains:

| Metric | Description |
|--------|-------------|
| Chain detection | Sequences of hops across multiple agents |
| Deceptive chains | Per-hop safe but end-to-end unsafe |
| Injection propagation | Prompt injection indicators along chain |
| Goal drift | Content transformation across hops |

**High risk indicators:** Deceptive chains, injection indicators in chain, long chains with many transforms.

### 7.6 Composite Risk Score

The composite team risk score combines all five signals:

```
R_team = 1 - PROD(1 - w_i * s_i)
```

Where `w_i` is the weight for signal family `i` and `s_i` is the risk score. Default weights are 0.2 for each family (equal weighting).

This formula ensures:
- A single high signal can elevate overall risk
- Multiple moderate signals compound
- All signals at zero yields zero composite risk
- The result is always in [0, 1]

---

## 8. Team Compliance Gate

### 8.1 Evaluation Point

The gate evaluates **synchronously** before each message delivery. It is the single point of enforcement for the compliance layer.

### 8.2 Inputs

| Input | Source |
|-------|--------|
| Message (sender, receiver, payload) | Adapter |
| Current manifest | Manifest store |
| R_team | Audit signal computation |
| Policy bindings | Configuration |
| Intervention history | Intervention layer |

### 8.3 Verdict Bands

| Score Range | Verdict | Description |
|-------------|---------|-------------|
| [0.00, 0.40) | ALLOW | Message delivered normally |
| [0.40, 0.65) | WARN | Message delivered with compliance warning |
| [0.65, 0.80) | THROTTLE | Message rate-limited via token bucket |
| [0.80, 0.92) | ISOLATE | Specific edge blocked |
| [0.92, 1.00] | TERMINATE | All team edges blocked permanently |

### 8.4 Compound Safety Class

The final verdict is the **most severe** of:

1. Verdict from R_team mapped through verdict bands
2. Minimum verdict from safety class (RESTRICTED -> WARN, HIGH_RISK -> THROTTLE)
3. Minimum verdict from active policy bindings
4. Current intervention state

### 8.5 Escalation from Capabilities

When aggregate capabilities cross escalation thresholds (Section 6.5), the safety class is elevated, which in turn elevates the minimum verdict:

| Safety Class | Minimum Verdict |
|-------------|-----------------|
| STANDARD | ALLOW |
| RESTRICTED | WARN |
| HIGH_RISK | THROTTLE |

### 8.6 Gate Result

The gate returns a structured result containing:

| Field | Type | Description |
|-------|------|-------------|
| verdict | Verdict | The compliance decision |
| r_team | float | Composite risk score |
| signal_scores | Dict[str, float] | Per-signal-family scores |
| safety_class | SafetyClass | Team safety classification |
| team_id | Optional[str] | Team identifier (if team detected) |
| manifest_version | Optional[int] | Manifest version at evaluation |
| evaluation_time_ms | float | Gate latency in milliseconds |
| reasons | List[str] | Human-readable reasons |

### 8.7 Determinism

The gate is deterministic: given identical inputs (message, manifest state, signal state, policy bindings, intervention history), it produces the identical verdict. This property is essential for replay-based auditing and testing.

---

## 9. Intervention Layer

### 9.1 Intervention Types

| Verdict | Action | Reversible | Cooldown |
|---------|--------|------------|----------|
| WARN | Log warning, attach header | Yes | 60s (default) |
| THROTTLE | Token bucket rate limiting | Yes | 60s (default) |
| ISOLATE | Block specific edge | Yes | 60s (default) |
| TERMINATE | Block all team edges | **No** | N/A |

### 9.2 Token Bucket Throttling

For THROTTLE verdicts, a token bucket is created per edge:

- **Capacity** = base_capacity * (1 - R_team)
- **Refill rate** = base_rate * (1 - R_team)
- Higher risk = smaller bucket = more aggressive throttling

### 9.3 Edge Isolation

For ISOLATE verdicts, the specific edge (sender, receiver) is blocked. Other edges within the same team remain open unless separately isolated.

### 9.4 Team Termination

For TERMINATE verdicts:

- All edges within the team are blocked within `terminate_deadline` seconds (default: 1.0)
- The termination is **irreversible** for the lifetime of the team
- The team state is set to TERMINATED

### 9.5 Cooldown and Release

WARN, THROTTLE, and ISOLATE interventions have a configurable cooldown period (default: 60 seconds). After the cooldown expires, the intervention is automatically released.

Manual release is possible with `release_edge()`, but:
- Release is blocked during cooldown (unless `force=True`)
- TERMINATE interventions cannot be released even with force

### 9.6 Determinism

Interventions are deterministic: given the same (verdict, edge, manifest_version), the same intervention is produced.

---

## 10. Team Audit Trail

### 10.1 Structure

The audit trail is an append-only log where each entry is linked to its predecessor via a SHA-256 hash chain.

### 10.2 Entry Format

| Field | Type | Description |
|-------|------|-------------|
| event_id | string | Unique event identifier (UUID) |
| event_type | EventType | Type of audit event |
| team_id | string | Team identifier |
| timestamp | float | Event timestamp (Unix epoch) |
| manifest_version | int | Manifest version at event time |
| r_team | float | Composite risk score at event time |
| verdict | string | Gate verdict at event time |
| affected_edges | List[(str, str)] | Edges affected by this event |
| payload_hash | string | Hash of the message payload |
| prev_hash | string | SHA-256 hash of the previous entry |
| entry_hash | string | SHA-256 hash of this entry |

### 10.3 Hash Chain

```
Genesis Hash = SHA-256("A2ASTC-GENESIS-v0.1.0")

Entry[0].prev_hash = Genesis Hash
Entry[0].entry_hash = SHA-256(canonical(Entry[0] without entry_hash))

Entry[n].prev_hash = Entry[n-1].entry_hash
Entry[n].entry_hash = SHA-256(canonical(Entry[n] without entry_hash))
```

The canonical form is JSON with sorted keys and no whitespace separators.

### 10.4 Required Event Types

| Event Type | Trigger |
|-----------|---------|
| TEAM_FORMED | New team detected |
| TEAM_MEMBER_JOINED | Agent added to team |
| TEAM_MEMBER_LEFT | Agent removed from team |
| TEAM_MERGED | Two teams merged |
| TEAM_MANIFEST_UPDATED | Manifest version bumped |
| TEAM_GATE_VERDICT | Gate evaluation completed |
| TEAM_WARN | WARN verdict issued |
| TEAM_THROTTLED | THROTTLE verdict issued |
| TEAM_EDGE_ISOLATED | ISOLATE verdict issued |
| TEAM_TERMINATED | TERMINATE verdict issued |
| TEAM_DISSOLVED | Team disbanded |
| TEAM_RISK_BAND_CHANGED | R_team crossed a verdict band boundary |
| TEAM_CAPABILITY_ESCALATION | Aggregate capabilities crossed escalation threshold |
| TEAM_SIDECHANNEL_DETECTED | Side-channel pattern detected |
| TEAM_DECEPTIVE_CASCADE_DETECTED | Deceptive cascade detected |

### 10.5 Retention

Default retention period: 365 days. Entries older than the retention period may be pruned. Pruning breaks the hash chain for older entries but the chain remains valid for retained entries.

### 10.6 Tamper Detection

Chain validation recomputes each entry's hash and verifies it matches the stored hash, and that each entry's prev_hash matches the previous entry's entry_hash. Any discrepancy indicates tampering and reports the index of the first broken entry.

---

## 11. Integration Contract

### 11.1 Adapter Interface

All adapters produce a normalized tuple: `(sender_id, receiver_id, payload, headers)`.

### 11.2 Supported Transports

| Adapter | Transport | Extraction Method |
|---------|-----------|-------------------|
| `A2AJsonRpcAdapter` | A2A 0.3.0 JSON-RPC | Extract from `params.metadata.sender_agent_id` / `receiver_agent_id` |
| `A2AGrpcAdapter` | A2A gRPC | Extract from gRPC metadata headers `x-a2a-sender-agent-id` / `x-a2a-receiver-agent-id` |
| `MCPBridgeAdapter` | MCP-bridged A2A | Extract from tool call context `caller_agent_id` and arguments `target_agent` |
| `GenericAdapter` | Direct tuples | Pass-through |

### 11.3 Middleware Hooks

The `TeamComplianceGate` provides four async hooks for framework integration:

| Hook | When | Returns |
|------|------|---------|
| `on_message_pre_dispatch` | Before message delivery | `GateResult` |
| `on_message_post_dispatch` | After successful delivery | None |
| `on_agent_disconnect` | Agent leaves the system | None |
| `on_shutdown` | System shutdown | None |

### 11.4 Synchronous Evaluation

The `evaluate()` method provides synchronous evaluation for cases where async is not needed or available.

### 11.5 Configuration

Priority: constructor args > environment variables (`A2ASTC_*`) > YAML file (`$A2ASTC_CONFIG`) > defaults.

All defaulted values are logged at INFO level.

---

## 12. Conformance Levels

### 12.1 Level 1: Detection (Minimum)

An implementation MUST:
- Detect team formation from bidirectional pairs
- Maintain a team manifest with members and capabilities
- Compute at least one signal family risk score
- Produce a verdict for each message

### 12.2 Level 2: Audit (Recommended)

An implementation MUST additionally:
- Compute all five signal families
- Compute composite R_team
- Maintain a hash-chained audit trail
- Support all 15 required event types

### 12.3 Level 3: Full Compliance (Required for Production)

An implementation MUST additionally:
- Pass all 15 TCK fixtures (positive detection AND negative non-detection)
- Support graduated interventions (WARN through TERMINATE)
- Support policy bindings
- Support all four transport adapters
- Meet latency targets (P50 < 5ms, P95 < 20ms, P99 < 50ms)

---

## 13. Adversarial Fixtures

The Team Compliance Kit (TCK) contains 15 adversarial fixtures. Each fixture defines:
- A positive scenario that SHOULD trigger detection
- A negative scenario that SHOULD NOT trigger detection
- The expected signal family
- The expected minimum verdict

| ID | Name | Signal | Min. Verdict |
|----|------|--------|-------------|
| TCK-001 | Capability Laundering | privilege | WARN |
| TCK-002 | Emergent Collusion | semantic | WARN |
| TCK-003 | Deceptive Cascade | cascade | THROTTLE |
| TCK-004 | Side-Channel Timing | sidechannel | WARN |
| TCK-005 | Side-Channel Length | sidechannel | WARN |
| TCK-006 | Steganography Metadata | sidechannel | WARN |
| TCK-007 | Privilege Aggregation | privilege | WARN |
| TCK-008 | Identity Multiplication | topology | WARN |
| TCK-009 | Prompt Injection Cascade | cascade | ISOLATE |
| TCK-010 | Coalition Against Third | topology | WARN |
| TCK-011 | Convergent Vocabulary | semantic | WARN |
| TCK-012 | Throttle Evasion | topology | THROTTLE |
| TCK-013 | Isolation Evasion | topology | ISOLATE |
| TCK-014 | Manifest Desync | topology | WARN |
| TCK-015 | Trail Tamper | cascade | TERMINATE |

### 13.1 Fixture Structure

Each fixture is a Python module with:

```python
FIXTURE_ID: str           # e.g., "TCK-001"
FIXTURE_NAME: str         # Human-readable name
FIXTURE_DESCRIPTION: str  # One-line description

expected_signal_family: str      # Which signal family should detect
expected_minimum_verdict: str    # Minimum expected verdict

def positive_scenario() -> List[Dict]:
    """Message sequence that SHOULD trigger detection."""
    ...

def negative_scenario() -> List[Dict]:
    """Similar but benign sequence that SHOULD NOT trigger."""
    ...
```

### 13.2 Pass Criteria

A fixture passes if:
1. The positive scenario produces a verdict at least as severe as `expected_minimum_verdict`
2. The negative scenario produces an ALLOW verdict

---

## 14. Operational Guarantees

### 14.1 Latency

| Percentile | Target | Notes |
|-----------|--------|-------|
| P50 | < 5ms | Typical evaluation |
| P95 | < 20ms | Including large teams |
| P99 | < 50ms | Worst case |

### 14.2 Memory

- Per-team memory: O(members * capabilities)
- Per-trail-entry memory: O(1) (fixed-size entries)
- Signal state: O(messages_in_window)

### 14.3 Availability

The gate MUST NOT crash on malformed inputs. All errors are caught and result in a default ALLOW verdict with an error flag, ensuring the compliance layer does not become a single point of failure.

### 14.4 Ordering

Events within a single team are totally ordered by the audit trail. Events across teams have no guaranteed ordering.

### 14.5 Idempotency

Replaying the same message sequence through a fresh gate instance produces the same sequence of verdicts (determinism guarantee from Section 8.7).

---

## 15. Schemas

Five JSON Schema definitions (draft 2020-12) are provided:

| Schema | Description |
|--------|-------------|
| `team-manifest.schema.json` | Team manifest structure |
| `team-audit-event.schema.json` | Audit trail entry structure |
| `gate-verdict.schema.json` | Gate evaluation result |
| `policy-binding.schema.json` | Policy binding configuration |
| `agent-record.schema.json` | Individual agent record |

All schemas use the `$id` base URI `https://a2astc.space/schemas/`.

---

## 16. Security Considerations

### 16.1 Threat Model

The compliance plane itself is a security-critical component. Key threats:

| Threat | Description | Mitigation |
|--------|-------------|------------|
| Trail Tampering | Modification of audit entries | SHA-256 hash chain, external anchoring |
| Manifest Desync | Manifest disagrees with actual membership | Derived from detector state |
| Gate Bypass | Messages delivered without gate evaluation | Mandatory middleware deployment |
| Signal Evasion | Structured communication to avoid signals | Five orthogonal signal families |
| Configuration Manipulation | Weakening verdicts via config | OS-level access controls |
| DoS via False Positives | Deliberate triggering of high risk | Cooldown periods, manual release |
| Clock Manipulation | False timestamps to evade windows | Server-side timestamp enforcement |
| Identity Spoofing | Claiming another agent's identity | Transport-layer identity binding |
| Side-Channel in Compliance | Using verdicts as covert channel | Do not expose verdicts to agents |
| Resource Exhaustion | Overwhelming the gate | Lightweight evaluation, transport rate limiting |

### 16.2 Recommendations

1. Deploy the gate as mandatory middleware with no bypass paths
2. Protect configuration with file system permissions
3. Use server-side timestamps for detection
4. Bind agent identity at the transport layer
5. Do not expose verdicts or trail events to agents
6. Validate the hash chain periodically
7. Export trail data to external immutable storage
8. Rate-limit message ingestion at the transport layer
9. Monitor gate evaluation latency
10. Run conformance tests after configuration changes

---

## 17. Versioning

### 17.1 Specification Version

This specification uses semantic versioning: `MAJOR.MINOR.PATCH`.

- **MAJOR**: Breaking changes to the gate interface, verdict semantics, or audit trail format
- **MINOR**: New signal families, new event types, new optional fields
- **PATCH**: Clarifications, typo fixes, non-normative changes

### 17.2 Compatibility

Implementations MUST advertise the specification version they implement. The reference implementation includes `__version__` matching the spec version.

### 17.3 Extension Points

Implementations MAY add:
- Custom signal families (in addition to the five required)
- Custom event types (in addition to the 15 required)
- Custom verdict bands (overriding defaults via configuration)
- Custom adapters (in addition to the four provided)

Extensions MUST NOT alter the semantics of existing signals, event types, or verdicts.

---

## 18. Repository Layout

```
a2astc-protocol/
+-- pyproject.toml                  # PyPI: thinkneo-a2astc
+-- LICENSE                         # Apache-2.0
+-- README.md
+-- SPEC.md                         # This document
+-- src/thinkneo_a2astc/
|   +-- __init__.py                 # Exports TeamComplianceGate
|   +-- detector.py                 # Team detection (Section 5)
|   +-- manifest.py                 # Team manifest (Section 6)
|   +-- audit/
|   |   +-- __init__.py
|   |   +-- topology.py             # Communication topology signals
|   |   +-- semantic.py             # Semantic convergence signals
|   |   +-- privilege.py            # Privilege aggregation signals
|   |   +-- sidechannel.py          # Side-channel detection signals
|   |   +-- cascade.py              # Deceptive cascade detection
|   +-- gate.py                     # Team Compliance Gate (Section 8)
|   +-- intervention.py             # Intervention layer (Section 9)
|   +-- trail.py                    # Team Audit Trail (Section 10)
|   +-- adapters/
|   |   +-- __init__.py
|   |   +-- a2a_jsonrpc.py          # A2A 0.3.0 JSON-RPC adapter
|   |   +-- a2a_grpc.py             # A2A gRPC adapter
|   |   +-- mcp_bridge.py           # MCP-bridged A2A adapter
|   |   +-- generic.py              # Generic adapter
|   +-- config.py                   # Configuration loading (Section 11.5)
|   +-- schemas/
|       +-- __init__.py
|       +-- team-manifest.schema.json
|       +-- team-audit-event.schema.json
|       +-- gate-verdict.schema.json
|       +-- policy-binding.schema.json
|       +-- agent-record.schema.json
+-- conformance/
|   +-- __init__.py
|   +-- fixtures/
|   |   +-- __init__.py
|   |   +-- capability_laundering.py
|   |   +-- emergent_collusion.py
|   |   +-- deceptive_cascade.py
|   |   +-- sidechannel_timing.py
|   |   +-- sidechannel_length.py
|   |   +-- steganography_metadata.py
|   |   +-- privilege_aggregation.py
|   |   +-- identity_multiplication.py
|   |   +-- prompt_injection_cascade.py
|   |   +-- coalition_against_third.py
|   |   +-- convergent_vocabulary.py
|   |   +-- throttle_evasion.py
|   |   +-- isolation_evasion.py
|   |   +-- manifest_desync.py
|   |   +-- trail_tamper.py
|   +-- INDEX.md
|   +-- runner.py
+-- tests/
|   +-- __init__.py
|   +-- test_detector.py
|   +-- test_manifest.py
|   +-- test_audit_topology.py
|   +-- test_audit_semantic.py
|   +-- test_audit_privilege.py
|   +-- test_audit_sidechannel.py
|   +-- test_audit_cascade.py
|   +-- test_gate.py
|   +-- test_intervention.py
|   +-- test_trail.py
|   +-- test_config.py
|   +-- test_adapters.py
|   +-- test_conformance.py
+-- benchmarks/
|   +-- __init__.py
|   +-- bench_gate.py
+-- docs/
    +-- integration-guide.md
    +-- policy-authoring.md
    +-- operations-runbook.md
    +-- threat-model.md
```

---

## 19. Commercial Positioning

### 19.1 Open-Source Core

The A2ASTC specification and reference implementation are open-source under the Apache-2.0 license. Any organization may implement, deploy, and extend A2ASTC without licensing fees.

### 19.2 ThinkNEO Managed Service

ThinkNEO offers a managed A2ASTC service with:
- Hosted gate evaluation with SLA-backed latency
- Persistent audit trail with external hash anchoring
- Dashboard for team monitoring and incident investigation
- Custom signal development
- Conformance certification

### 19.3 Ecosystem

A2ASTC is designed to complement existing standards:
- **A2A Protocol (Google)**: A2ASTC monitors A2A messages
- **MCP (Anthropic)**: A2ASTC bridges MCP tool calls
- **EU AI Act**: A2ASTC provides audit trail capabilities for high-risk AI system compliance
- **NIST AI RMF**: A2ASTC addresses multi-agent governance gaps

---

## 20. Acknowledgments and Change Log

### 20.1 Acknowledgments

A2ASTC was developed by ThinkNEO AI Technology Company Limited, Hong Kong.

The specification builds on insights from:
- The Agent-to-Agent (A2A) Protocol community
- The Model Context Protocol (MCP) specification
- Research on emergent behavior in multi-agent systems
- Practical experience operating 19+ AI agents in production

### 20.2 Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-05-01 | Initial release. 20 sections, 5 signal families, 15 TCK fixtures. |

---

*Copyright 2026 ThinkNEO AI Technology Company Limited. Licensed under Apache-2.0.*
