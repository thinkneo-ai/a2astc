# A2ASTC Threat Model

## Scope

This document describes the threat model for the A2ASTC compliance plane
itself -- the threats to the compliance layer, not the threats it detects
(those are covered in the specification Section 16).

## Assets

| Asset | Criticality | Description |
|-------|-------------|-------------|
| Audit Trail | High | Append-only hash-chained event log |
| Team Manifests | High | Authoritative team membership and capability records |
| Gate Verdicts | High | Compliance decisions that affect message delivery |
| Configuration | Medium | Policy bindings, verdict bands, weights |
| Signal State | Medium | Accumulated audit signal data |

## Threat Actors

### T1: Malicious Agent
An agent within the A2A system that attempts to subvert the compliance layer.

### T2: Compromised Operator
An operator with legitimate access who misuses configuration capabilities.

### T3: External Attacker
An attacker without direct agent access who targets the compliance infrastructure.

### T4: Colluding Agents
Multiple agents that coordinate to evade detection.

## Threats and Mitigations

### TH-01: Trail Tampering
**Actor:** T1, T2
**Description:** Modification of audit trail entries to hide evidence.
**Mitigation:** SHA-256 hash chain makes tampering detectable. Each entry
links to its predecessor, and recomputation of hashes reveals modifications.
**Residual Risk:** If the attacker controls the trail storage, they could
rebuild the chain. External hash anchoring (e.g., blockchain) can mitigate.

### TH-02: Manifest Desynchronization
**Actor:** T1, T4
**Description:** Causing the manifest to disagree with actual team membership.
**Mitigation:** Manifests are derived from the detector state, which is based
on observed edges. Agents cannot directly modify manifests.
**Residual Risk:** If detection is delayed, there is a window of desync.

### TH-03: Gate Bypass
**Actor:** T1, T3
**Description:** Messages delivered without passing through the gate.
**Mitigation:** The gate must be deployed as mandatory middleware in the
message delivery path. See integration patterns in the integration guide.
**Residual Risk:** Misconfigured deployments that leave alternate paths open.

### TH-04: Signal Evasion
**Actor:** T4
**Description:** Agents structure communication to avoid triggering signals.
**Mitigation:** Multiple orthogonal signals (topology, semantic, privilege,
sidechannel, cascade) make evasion of all signals simultaneously difficult.
The composite risk formula means even moderate signals combine to elevate risk.
**Residual Risk:** Sufficiently sophisticated adversaries may find blind spots.

### TH-05: Configuration Manipulation
**Actor:** T2
**Description:** Weakening verdict bands, disabling signals, or removing policies.
**Mitigation:** Configuration changes should be logged and reviewed.
Protect the YAML config file and environment variables with OS-level ACLs.
**Residual Risk:** Operators with root access can always bypass.

### TH-06: Denial of Service via False Positives
**Actor:** T1, T4
**Description:** Agents deliberately trigger high risk scores to cause
legitimate teams to be throttled or isolated.
**Mitigation:** Reversible interventions (WARN, THROTTLE, ISOLATE) have
cooldown periods. Operators can manually release edges. TERMINATE is the
only irreversible action and requires very high risk scores.
**Residual Risk:** Short-term disruption is possible before cooldown expires.

### TH-07: Clock Manipulation
**Actor:** T1
**Description:** Agents provide false timestamps to evade window-based detection.
**Mitigation:** The gate should use server-side timestamps rather than
agent-provided timestamps for detection window calculations.
**Residual Risk:** If agents can manipulate server clocks, detection is weakened.

### TH-08: Identity Spoofing
**Actor:** T1
**Description:** An agent claims another agent's identity to bypass per-agent limits.
**Mitigation:** Agent identity should be verified at the transport layer
(TLS client certificates, API keys, etc.) before reaching A2ASTC.
**Residual Risk:** Depends on transport-layer identity binding strength.

### TH-09: Side-Channel in Compliance Metadata
**Actor:** T4
**Description:** Agents use A2ASTC verdicts or trail events as a covert channel.
**Mitigation:** Verdicts and trail events should not be exposed to agents.
Only the ALLOW/block decision should be visible.
**Residual Risk:** Timing of block decisions may leak information.

### TH-10: Resource Exhaustion
**Actor:** T1, T3
**Description:** Overwhelming the compliance layer with rapid messages to
degrade gate evaluation performance.
**Mitigation:** The gate evaluation path is designed to be lightweight
(sub-millisecond for typical teams). Rate limiting at the transport layer
provides defense in depth.
**Residual Risk:** Very large teams (100+ members) may increase evaluation latency.

## Security Recommendations

1. **Deploy the gate as mandatory middleware** - no alternate message paths.
2. **Protect configuration** with file system permissions and audit logging.
3. **Use server-side timestamps** for detection, not agent-provided timestamps.
4. **Bind agent identity** at the transport layer before reaching A2ASTC.
5. **Do not expose verdicts** or trail events directly to agents.
6. **Periodically validate the hash chain** and alert on failures.
7. **Export trail data** to external immutable storage for forensics.
8. **Rate-limit message ingestion** at the transport layer.
9. **Monitor gate evaluation latency** and alert on degradation.
10. **Run conformance tests** after any configuration or code changes.
