# A2ASTC Policy Authoring Guide

## Overview

Policies in A2ASTC are bindings that influence gate decisions beyond
the default risk-score-to-verdict mapping. They allow operators to
encode organization-specific compliance requirements.

## Policy Structure

```python
from thinkneo_a2astc.gate import PolicyBinding

policy = PolicyBinding(
    policy_id="policy-001",
    name="Block Code Execution in Production",
    description="Prevent any team with code-exec from operating in production",
    blocked_capabilities={"code-exec"},
    signal_minimums={"cascade": "ISOLATE"},
    active=True,
)
```

## Policy Fields

### policy_id (required)
Unique identifier for the policy. Use a stable ID that can be
referenced in audit trails and incident reports.

### name (required)
Human-readable name for the policy.

### description (optional)
Detailed description of what the policy enforces and why.

### blocked_capabilities (optional)
A set of capability strings. If any team member possesses any
of these capabilities, the gate will elevate to at least ISOLATE.

Example: `{"code-exec", "identity-assumption"}`

### custom_bands (optional)
Override the default verdict bands for messages matching this policy.

```python
custom_bands=[
    (0.0, 0.3, "ALLOW"),
    (0.3, 0.6, "WARN"),
    (0.6, 1.01, "TERMINATE"),
]
```

### signal_minimums (optional)
Per-signal-family minimum verdicts. When a signal's score exceeds 0.5,
the specified minimum verdict is applied.

```python
signal_minimums={
    "cascade": "ISOLATE",       # Any cascade detection triggers ISOLATE
    "sidechannel": "THROTTLE",  # Side-channel detection triggers THROTTLE
}
```

### active (default: True)
Whether this policy is currently enforced. Inactive policies are
ignored during gate evaluation.

## Common Patterns

### Deny-list Policy

Block specific capability combinations:

```python
PolicyBinding(
    policy_id="deny-exec-egress",
    name="Deny Code Exec + Network Egress",
    blocked_capabilities={"code-exec", "net-egress"},
)
```

### Strict Mode Policy

Tighter verdict bands for sensitive environments:

```python
PolicyBinding(
    policy_id="strict-mode",
    name="Strict Compliance Mode",
    custom_bands=[
        (0.0, 0.2, "ALLOW"),
        (0.2, 0.4, "WARN"),
        (0.4, 0.6, "THROTTLE"),
        (0.6, 0.8, "ISOLATE"),
        (0.8, 1.01, "TERMINATE"),
    ],
)
```

### Signal-Specific Policy

React strongly to specific signal families:

```python
PolicyBinding(
    policy_id="anti-sidechannel",
    name="Zero Tolerance for Side-Channels",
    signal_minimums={
        "sidechannel": "TERMINATE",
    },
)
```

## Adding Policies to the Gate

```python
from thinkneo_a2astc import TeamComplianceGate
from thinkneo_a2astc.gate import PolicyBinding

gate = TeamComplianceGate()

gate.add_policy(PolicyBinding(
    policy_id="my-policy",
    name="My Custom Policy",
    blocked_capabilities={"identity-assumption"},
))

# Remove a policy
gate.remove_policy("my-policy")
```

## Policy Evaluation Order

1. Risk score mapped to verdict via bands (default or custom)
2. Safety class mapped to minimum verdict
3. All active policies evaluated
4. Compound verdict = maximum severity across all sources
5. Intervention state checked (may further elevate)

## Best Practices

1. **Start permissive, tighten gradually.** Begin with WARN-level policies
   and escalate to THROTTLE/ISOLATE as you gain confidence.

2. **Use descriptive policy IDs.** They appear in audit trails.

3. **Document the "why".** Use the description field liberally.

4. **Test with conformance fixtures.** Run the TCK against your
   policy configuration before deploying.

5. **Monitor false positives.** Review WARN verdicts to calibrate
   signal weights and verdict bands.

## Policy Schema

Policies can be serialized as JSON. See `schemas/policy-binding.schema.json`
for the formal schema definition.
