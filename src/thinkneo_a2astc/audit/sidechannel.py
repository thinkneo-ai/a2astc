"""
Side-Channel Detection Signals (Section 6.4).

Detects covert communication channels between agents:
- Timing patterns (inter-message delay variance)
- Message length patterns (length parity / modular encoding)
- Ordering patterns (suspicious message sequencing)
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TimingRecord:
    """Record of message timing for an edge."""

    sender: str
    receiver: str
    timestamp: float
    message_length: int


@dataclass
class SideChannelSnapshot:
    """Snapshot of side-channel analysis metrics."""

    timing_regularity: float = 0.0  # 0 = irregular, 1 = very regular
    length_pattern_score: float = 0.0
    ordering_anomaly: float = 0.0
    detected_patterns: List[str] = field(default_factory=list)
    risk_score: float = 0.0


class SideChannelSignal:
    """Detects covert side-channel communication patterns.

    Analyzes timing, message length, and ordering patterns that
    could indicate steganographic or covert communication.
    """

    def __init__(self) -> None:
        # Per-edge timing records
        self._edge_records: Dict[Tuple[str, str], List[TimingRecord]] = defaultdict(
            list
        )
        # Global message ordering
        self._global_order: List[TimingRecord] = []

    def record_message(
        self,
        sender: str,
        receiver: str,
        timestamp: float,
        message_length: int,
    ) -> None:
        """Record message metadata for side-channel analysis."""
        record = TimingRecord(
            sender=sender,
            receiver=receiver,
            timestamp=timestamp,
            message_length=message_length,
        )
        self._edge_records[(sender, receiver)].append(record)
        self._global_order.append(record)

    def evaluate(self, team_members: Set[str]) -> SideChannelSnapshot:
        """Evaluate side-channel risk for a team.

        Args:
            team_members: Set of agent IDs to evaluate.

        Returns:
            SideChannelSnapshot with detection results and risk score.
        """
        if len(team_members) < 2:
            return SideChannelSnapshot(risk_score=0.0)

        # Filter to team edges
        team_edges: Dict[Tuple[str, str], List[TimingRecord]] = {}
        for (s, r), records in self._edge_records.items():
            if s in team_members and r in team_members:
                team_edges[(s, r)] = records

        if not team_edges:
            return SideChannelSnapshot(risk_score=0.0)

        # Analyze timing patterns
        timing_score, timing_patterns = self._analyze_timing(team_edges)

        # Analyze message length patterns
        length_score, length_patterns = self._analyze_lengths(team_edges)

        # Analyze ordering patterns
        ordering_score, ordering_patterns = self._analyze_ordering(
            team_members
        )

        all_patterns = timing_patterns + length_patterns + ordering_patterns

        risk_score = _compute_sidechannel_risk(
            timing_score=timing_score,
            length_score=length_score,
            ordering_score=ordering_score,
        )

        return SideChannelSnapshot(
            timing_regularity=timing_score,
            length_pattern_score=length_score,
            ordering_anomaly=ordering_score,
            detected_patterns=all_patterns,
            risk_score=max(0.0, min(1.0, risk_score)),
        )

    def _analyze_timing(
        self, edges: Dict[Tuple[str, str], List[TimingRecord]]
    ) -> Tuple[float, List[str]]:
        """Analyze inter-message timing patterns.

        Very regular timing intervals suggest automated/coordinated behavior.
        """
        patterns: List[str] = []
        regularity_scores: List[float] = []

        for (sender, receiver), records in edges.items():
            if len(records) < 3:
                continue

            # Compute inter-message delays
            timestamps = sorted(r.timestamp for r in records)
            delays = [
                timestamps[i + 1] - timestamps[i]
                for i in range(len(timestamps) - 1)
            ]

            if not delays:
                continue

            mean_delay = statistics.mean(delays)
            if mean_delay == 0:
                regularity_scores.append(1.0)
                patterns.append(
                    f"timing:zero_delay:{sender}->{receiver}"
                )
                continue

            # Coefficient of variation (low = regular)
            if len(delays) >= 2:
                std_delay = statistics.stdev(delays)
                cv = std_delay / mean_delay if mean_delay > 0 else 0

                # Regularity: inverse of CV, clamped to [0, 1]
                regularity = max(0.0, min(1.0, 1.0 - cv))
                regularity_scores.append(regularity)

                if regularity > 0.85:
                    patterns.append(
                        f"timing:high_regularity:{sender}->{receiver}"
                    )

                # Check for exact periodicity
                if cv < 0.05 and mean_delay > 0:
                    patterns.append(
                        f"timing:periodic:{sender}->{receiver}:period={mean_delay:.3f}s"
                    )

        avg_regularity = (
            sum(regularity_scores) / len(regularity_scores)
            if regularity_scores
            else 0.0
        )
        return avg_regularity, patterns

    def _analyze_lengths(
        self, edges: Dict[Tuple[str, str], List[TimingRecord]]
    ) -> Tuple[float, List[str]]:
        """Analyze message length patterns.

        Detects modular encoding (lengths mod N follow a pattern)
        and parity-based signaling.
        """
        patterns: List[str] = []
        length_scores: List[float] = []

        for (sender, receiver), records in edges.items():
            if len(records) < 5:
                continue

            lengths = [r.message_length for r in records]

            # Check parity distribution (should be ~50/50 for natural messages)
            even_count = sum(1 for l in lengths if l % 2 == 0)
            parity_ratio = even_count / len(lengths)
            parity_deviation = abs(parity_ratio - 0.5) * 2  # 0 = balanced, 1 = all same

            if parity_deviation > 0.7:
                patterns.append(
                    f"length:parity_bias:{sender}->{receiver}:ratio={parity_ratio:.2f}"
                )
                length_scores.append(parity_deviation)

            # Check modular patterns (mod 3, mod 5, mod 8)
            for mod in [3, 5, 8]:
                remainders = [l % mod for l in lengths]
                remainder_counts = [remainders.count(i) for i in range(mod)]
                expected = len(lengths) / mod

                if expected > 0:
                    chi_sq = sum(
                        (obs - expected) ** 2 / expected
                        for obs in remainder_counts
                    )
                    # Normalize chi-squared
                    norm_chi = chi_sq / (len(lengths) * mod)
                    if norm_chi > 0.5:
                        patterns.append(
                            f"length:modular:{sender}->{receiver}:mod={mod}"
                        )
                        length_scores.append(min(1.0, norm_chi))

            # Check for length clustering (many messages of exactly same length)
            from collections import Counter

            length_counter = Counter(lengths)
            most_common_freq = length_counter.most_common(1)[0][1] / len(lengths)
            if most_common_freq > 0.5:
                patterns.append(
                    f"length:clustering:{sender}->{receiver}"
                )
                length_scores.append(most_common_freq)

        avg_score = (
            sum(length_scores) / len(length_scores) if length_scores else 0.0
        )
        return avg_score, patterns

    def _analyze_ordering(
        self, team_members: Set[str]
    ) -> Tuple[float, List[str]]:
        """Analyze message ordering patterns.

        Detects suspicious turn-taking or coordination patterns.
        """
        patterns: List[str] = []

        # Filter to team messages
        team_messages = [
            r for r in self._global_order
            if r.sender in team_members and r.receiver in team_members
        ]

        if len(team_messages) < 4:
            return 0.0, patterns

        # Check for strict alternation between specific pairs
        sender_sequence = [m.sender for m in team_messages]

        # Look for repeating sub-sequences
        seq_len = len(sender_sequence)
        for period in range(2, min(seq_len // 2, 5) + 1):
            pattern = sender_sequence[:period]
            matches = 0
            total_checks = 0
            for i in range(seq_len):
                if sender_sequence[i] == pattern[i % period]:
                    matches += 1
                total_checks += 1

            if total_checks > 0:
                match_ratio = matches / total_checks
                if match_ratio > 0.8:
                    patterns.append(
                        f"ordering:periodic_sender:period={period}"
                    )
                    return match_ratio, patterns

        # Check for strict request-response pairing
        pair_count = 0
        for i in range(0, len(team_messages) - 1, 2):
            if (
                team_messages[i].sender == team_messages[i + 1].receiver
                and team_messages[i].receiver == team_messages[i + 1].sender
            ):
                pair_count += 1

        expected_pairs = len(team_messages) // 2
        if expected_pairs > 0:
            pair_ratio = pair_count / expected_pairs
            if pair_ratio > 0.8:
                patterns.append("ordering:strict_request_response")
                return pair_ratio * 0.3, patterns  # Lower weight, this can be normal

        return 0.0, patterns

    def clear(self) -> None:
        """Reset all tracked state."""
        self._edge_records.clear()
        self._global_order.clear()


def _compute_sidechannel_risk(
    timing_score: float,
    length_score: float,
    ordering_score: float,
) -> float:
    """Compute composite side-channel risk score in [0, 1]."""
    risk = 0.0

    # Timing regularity (highly regular = suspicious)
    if timing_score > 0.9:
        risk += 0.4
    elif timing_score > 0.7:
        risk += 0.25
    elif timing_score > 0.5:
        risk += 0.1

    # Length pattern score
    if length_score > 0.7:
        risk += 0.35
    elif length_score > 0.4:
        risk += 0.2
    elif length_score > 0.2:
        risk += 0.1

    # Ordering anomaly
    if ordering_score > 0.7:
        risk += 0.25
    elif ordering_score > 0.4:
        risk += 0.15

    return max(0.0, min(1.0, risk))
