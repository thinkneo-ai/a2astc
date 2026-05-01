"""
Conformance Test Runner (Section 12).

Runs all conformance fixtures through the A2ASTC pipeline and
reports pass/fail results.
"""

from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from thinkneo_a2astc import TeamComplianceGate, A2ASTCConfig

logger = logging.getLogger("a2astc.conformance")


@dataclass
class FixtureResult:
    """Result of running a single conformance fixture."""

    fixture_id: str
    fixture_name: str
    positive_detected: bool
    negative_clean: bool
    passed: bool
    positive_verdict: Optional[str] = None
    negative_verdict: Optional[str] = None
    expected_signal: str = ""
    expected_minimum_verdict: str = ""
    actual_signal_score: float = 0.0
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ConformanceReport:
    """Full conformance test report."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    results: List[FixtureResult] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def pass_rate(self) -> float:
        """Conformance pass rate as percentage."""
        return (self.passed / self.total * 100) if self.total > 0 else 0.0


# Ordered verdict severity for comparison
VERDICT_ORDER = ["ALLOW", "WARN", "THROTTLE", "ISOLATE", "TERMINATE"]


def _verdict_at_least(actual: str, minimum: str) -> bool:
    """Check if actual verdict is at least as severe as minimum."""
    actual_idx = VERDICT_ORDER.index(actual) if actual in VERDICT_ORDER else -1
    min_idx = VERDICT_ORDER.index(minimum) if minimum in VERDICT_ORDER else -1
    return actual_idx >= min_idx


# List of all fixture module names
FIXTURE_MODULES = [
    "capability_laundering",
    "emergent_collusion",
    "deceptive_cascade",
    "sidechannel_timing",
    "sidechannel_length",
    "steganography_metadata",
    "privilege_aggregation",
    "identity_multiplication",
    "prompt_injection_cascade",
    "coalition_against_third",
    "convergent_vocabulary",
    "throttle_evasion",
    "isolation_evasion",
    "manifest_desync",
    "trail_tamper",
]


def _run_scenario(
    gate: TeamComplianceGate,
    messages: List[Dict[str, Any]],
) -> Optional[str]:
    """Run a message sequence through the gate and return the highest verdict."""
    highest_verdict = "ALLOW"

    for msg in messages:
        sender = msg.get("sender_id", "unknown")
        receiver = msg.get("receiver_id", "unknown")
        payload = msg.get("payload", "")
        timestamp = msg.get("timestamp")

        # Register agent capabilities if provided
        capabilities = msg.get("capabilities", {})
        for agent_id, caps in capabilities.items():
            gate.register_agent(agent_id, capabilities=caps)

        # Record data flows if provided
        data_flow = msg.get("data_flow")
        if data_flow:
            gate.privilege_signal.record_data_flow(
                sender=data_flow["sender"],
                receiver=data_flow["receiver"],
                capability_context=data_flow["capability"],
                timestamp=timestamp or time.time(),
            )

        # Record cascade hops if provided
        hop = msg.get("hop")
        if hop:
            gate.cascade_signal.record_hop(
                sender=sender,
                receiver=receiver,
                timestamp=timestamp or time.time(),
                content_hash=hop.get("content_hash", ""),
                safety_label=hop.get("safety_label", "safe"),
                transforms=hop.get("transforms", []),
                input_content_hash=hop.get("input_hash"),
            )

        # Record injection indicators
        injection = msg.get("injection_indicator")
        if injection:
            gate.cascade_signal.record_injection_indicator(
                agent_id=injection["agent"],
                pattern_type=injection["pattern"],
                timestamp=timestamp or time.time(),
            )

        # Evaluate through gate
        result = gate.evaluate(
            sender_id=sender,
            receiver_id=receiver,
            payload=payload,
            timestamp=timestamp,
        )

        if VERDICT_ORDER.index(result.verdict.value) > VERDICT_ORDER.index(highest_verdict):
            highest_verdict = result.verdict.value

    return highest_verdict


def run_fixture(fixture_module_name: str, config: Optional[A2ASTCConfig] = None) -> FixtureResult:
    """Run a single conformance fixture.

    Args:
        fixture_module_name: Name of the fixture module.
        config: Optional configuration override.

    Returns:
        FixtureResult with pass/fail information.
    """
    start = time.monotonic()

    try:
        module = importlib.import_module(
            f"conformance.fixtures.{fixture_module_name}"
        )
    except ImportError:
        return FixtureResult(
            fixture_id=f"TCK-???",
            fixture_name=fixture_module_name,
            positive_detected=False,
            negative_clean=False,
            passed=False,
            error=f"Could not import fixture module: {fixture_module_name}",
        )

    fixture_id = getattr(module, "FIXTURE_ID", "unknown")
    fixture_name = getattr(module, "FIXTURE_NAME", fixture_module_name)
    expected_signal = getattr(module, "expected_signal_family", "")
    expected_min = getattr(module, "expected_minimum_verdict", "WARN")

    try:
        # Run positive scenario (should detect)
        positive_gate = TeamComplianceGate(config=config or A2ASTCConfig())
        positive_messages = module.positive_scenario()
        positive_verdict = _run_scenario(positive_gate, positive_messages)
        positive_detected = _verdict_at_least(positive_verdict or "ALLOW", expected_min)

        # Run negative scenario (should not detect)
        negative_gate = TeamComplianceGate(config=config or A2ASTCConfig())
        negative_messages = module.negative_scenario()
        negative_verdict = _run_scenario(negative_gate, negative_messages)
        negative_clean = negative_verdict == "ALLOW"

        elapsed = (time.monotonic() - start) * 1000

        return FixtureResult(
            fixture_id=fixture_id,
            fixture_name=fixture_name,
            positive_detected=positive_detected,
            negative_clean=negative_clean,
            passed=positive_detected and negative_clean,
            positive_verdict=positive_verdict,
            negative_verdict=negative_verdict,
            expected_signal=expected_signal,
            expected_minimum_verdict=expected_min,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return FixtureResult(
            fixture_id=fixture_id,
            fixture_name=fixture_name,
            positive_detected=False,
            negative_clean=False,
            passed=False,
            error=str(e),
            duration_ms=elapsed,
        )


def run_all(config: Optional[A2ASTCConfig] = None) -> ConformanceReport:
    """Run all conformance fixtures and generate a report.

    Args:
        config: Optional configuration override.

    Returns:
        ConformanceReport with aggregate results.
    """
    report = ConformanceReport()
    start = time.monotonic()

    for module_name in FIXTURE_MODULES:
        result = run_fixture(module_name, config)
        report.results.append(result)
        report.total += 1

        if result.error:
            report.errors += 1
        elif result.passed:
            report.passed += 1
        else:
            report.failed += 1

        logger.info(
            "Fixture %s (%s): %s [pos=%s neg=%s] %.1fms",
            result.fixture_id,
            result.fixture_name,
            "PASS" if result.passed else "FAIL",
            result.positive_verdict,
            result.negative_verdict,
            result.duration_ms,
        )

    report.duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "Conformance: %d/%d passed (%.1f%%) in %.1fms",
        report.passed,
        report.total,
        report.pass_rate,
        report.duration_ms,
    )

    return report
