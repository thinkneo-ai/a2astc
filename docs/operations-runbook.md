# A2ASTC Operations Runbook

## Deployment

### Installation

```bash
pip install thinkneo-a2astc
```

### Configuration

A2ASTC configuration follows a priority chain:

1. **Constructor arguments** (highest priority)
2. **Environment variables** (`A2ASTC_*` prefix)
3. **YAML configuration file** (`$A2ASTC_CONFIG`)
4. **Built-in defaults** (lowest priority)

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `A2ASTC_TEAM_WINDOW` | `600.0` | Sliding window for team detection (seconds) |
| `A2ASTC_MIN_TEAM_SIZE` | `2` | Minimum agents to form a team |
| `A2ASTC_THROTTLE_BUCKET_CAPACITY` | `10.0` | Token bucket capacity |
| `A2ASTC_THROTTLE_BUCKET_REFILL_RATE` | `1.0` | Tokens per second |
| `A2ASTC_COOLDOWN_INTERVAL` | `60.0` | Cooldown for reversible interventions (seconds) |
| `A2ASTC_TRAIL_RETENTION_DAYS` | `365` | Audit trail retention period |
| `A2ASTC_TERMINATE_DEADLINE` | `1.0` | Seconds to block all edges on TERMINATE |
| `A2ASTC_LOG_LEVEL` | `INFO` | Logging level |
| `A2ASTC_CONFIG` | (none) | Path to YAML configuration file |

#### YAML Configuration

```yaml
team_window: 300.0
cooldown_interval: 30.0
throttle_bucket_capacity: 20.0
throttle_bucket_refill_rate: 2.0
trail_retention_days: 730
log_level: DEBUG
audit_weights:
  topology: 0.25
  semantic: 0.15
  privilege: 0.25
  sidechannel: 0.20
  cascade: 0.15
```

## Monitoring

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `a2astc.gate.evaluation_time_ms` | Gate latency | P99 > 50ms |
| `a2astc.gate.verdict.{ALLOW,WARN,...}` | Verdict distribution | TERMINATE > 0 |
| `a2astc.teams.active_count` | Number of active teams | Depends on system |
| `a2astc.teams.risk_score` | Current team risk scores | > 0.8 |
| `a2astc.trail.entry_count` | Audit trail size | Growing monotonically |
| `a2astc.interventions.active` | Active interventions | Any TERMINATE |

### Logging

A2ASTC uses Python's `logging` module with the `a2astc.*` logger hierarchy:

- `a2astc.config` - Configuration loading events
- `a2astc.detector` - Team formation/dissolution
- `a2astc.gate` - Gate evaluations
- `a2astc.intervention` - Intervention actions
- `a2astc.trail` - Audit trail events

```python
import logging
logging.getLogger("a2astc").setLevel(logging.DEBUG)
```

## Alerting

### Critical Alerts

1. **TERMINATE verdict issued** - Immediate investigation required.
   Check trail for team_id, inspect the message chain.

2. **Hash chain validation failure** - Potential trail tampering.
   Preserve the trail data and investigate.

3. **Gate evaluation latency spike** - Performance degradation.
   Check team sizes and audit signal computation.

### Warning Alerts

1. **Sustained THROTTLE verdicts** - Investigate whether legitimate
   or indicative of ongoing attack.

2. **Rapid team formation** - Many teams forming quickly may
   indicate identity multiplication attack.

## Troubleshooting

### Gate Always Returns ALLOW

1. Verify agents are communicating bidirectionally (team must form).
2. Check that capabilities are registered with `register_agent()`.
3. Verify the team window is long enough for your message cadence.

### High False Positive Rate

1. Review audit weights - reduce weights for noisy signals.
2. Adjust verdict bands - widen the ALLOW band.
3. Check if agents have legitimate reasons for high similarity.

### Trail Validation Failure

1. Check for out-of-process trail modification.
2. Verify no concurrent writers to the same trail instance.
3. If legitimate, re-initialize the trail from last known good state.

### Memory Growth

1. Call `trail.prune_expired()` periodically.
2. Monitor team count - dissolved teams remain in memory.
3. Set shorter `team_window` if teams are ephemeral.

## Backup and Recovery

### Trail Export

```python
data = trail.export_entries(team_id="specific-team")
# Write to persistent storage
```

### Trail Import

```python
count = trail.import_entries(data)
# Validates chain integrity during import
```

## Conformance Verification

Run the conformance test kit periodically:

```python
from conformance.runner import run_all

report = run_all()
assert report.pass_rate > 90.0, f"Conformance dropped to {report.pass_rate}%"
```
