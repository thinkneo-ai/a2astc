"""
Gate Evaluation Benchmarks.

Measures P50, P95, P99 latency for the TeamComplianceGate.evaluate() path.
Run with: pytest benchmarks/bench_gate.py -v --benchmark-only
"""

import time
import pytest
from thinkneo_a2astc import TeamComplianceGate, A2ASTCConfig


@pytest.fixture
def gate() -> TeamComplianceGate:
    """Create a fresh gate for each benchmark."""
    return TeamComplianceGate()


@pytest.fixture
def warmed_gate() -> TeamComplianceGate:
    """Create a gate with an already-formed team."""
    g = TeamComplianceGate()
    g.register_agent("bench-a", capabilities={"read-untrusted"})
    g.register_agent("bench-b", capabilities={"write-trusted"})
    g.evaluate("bench-a", "bench-b", "warmup-1", 1000.0)
    g.evaluate("bench-b", "bench-a", "warmup-2", 1001.0)
    return g


def test_gate_evaluate_cold(benchmark, gate):
    """Benchmark cold gate evaluation (no prior state)."""

    counter = [0]

    def run():
        counter[0] += 1
        gate_fresh = TeamComplianceGate()
        gate_fresh.evaluate(
            f"agent-{counter[0]}-a",
            f"agent-{counter[0]}-b",
            "benchmark payload for cold evaluation",
            1000.0 + counter[0],
        )

    benchmark(run)


def test_gate_evaluate_warm(benchmark, warmed_gate):
    """Benchmark warm gate evaluation (team already formed)."""

    counter = [0]

    def run():
        counter[0] += 1
        warmed_gate.evaluate(
            "bench-a",
            "bench-b",
            f"benchmark payload iteration {counter[0]}",
            2000.0 + counter[0] * 0.001,
        )

    benchmark(run)


def test_gate_evaluate_team_formation(benchmark):
    """Benchmark team formation through gate."""

    counter = [0]

    def run():
        counter[0] += 1
        g = TeamComplianceGate()
        g.evaluate(f"a-{counter[0]}", f"b-{counter[0]}", "hello", 1000.0)
        g.evaluate(f"b-{counter[0]}", f"a-{counter[0]}", "hi", 1001.0)

    benchmark(run)


def test_gate_evaluate_with_capabilities(benchmark):
    """Benchmark gate evaluation with registered capabilities."""

    counter = [0]

    def run():
        counter[0] += 1
        g = TeamComplianceGate()
        g.register_agent(f"reader-{counter[0]}", capabilities={"read-untrusted", "code-exec"})
        g.register_agent(f"writer-{counter[0]}", capabilities={"write-trusted", "net-egress"})
        g.evaluate(f"reader-{counter[0]}", f"writer-{counter[0]}", "data transfer", 1000.0)
        g.evaluate(f"writer-{counter[0]}", f"reader-{counter[0]}", "ack", 1001.0)

    benchmark(run)


def test_gate_evaluate_large_team(benchmark):
    """Benchmark gate evaluation with a large team."""

    def run():
        g = TeamComplianceGate()
        # Form a team with 10 members
        base = 1000.0
        for i in range(10):
            a = f"agent-{i}"
            b = f"agent-{(i + 1) % 10}"
            g.evaluate(a, b, f"message {i}", base + i)
            g.evaluate(b, a, f"reply {i}", base + i + 0.5)

    benchmark(run)
