"""
Semantic Convergence Signals (Section 6.2).

Detects when agents' message content converges in suspicious ways:
- Objective convergence (agents aligning on unexpected goals)
- Vocabulary specialization (shared jargon development)
- TF-IDF / character n-gram based similarity tracking
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class SemanticSnapshot:
    """Snapshot of semantic convergence metrics."""

    avg_pairwise_similarity: float = 0.0
    vocabulary_overlap: float = 0.0
    convergence_trend: float = 0.0  # positive = converging
    specialized_terms: List[str] = field(default_factory=list)
    risk_score: float = 0.0


class SemanticSignal:
    """Tracks message content for semantic convergence patterns.

    Uses character n-gram and term frequency vectors for lightweight
    similarity computation without requiring ML model dependencies.
    """

    def __init__(self, ngram_size: int = 3, window_size: int = 50) -> None:
        self._ngram_size = ngram_size
        self._window_size = window_size
        # Per-agent message history
        self._agent_messages: Dict[str, List[str]] = defaultdict(list)
        # Per-agent n-gram frequency vectors
        self._agent_ngrams: Dict[str, Counter] = defaultdict(Counter)
        # Per-agent term frequency
        self._agent_terms: Dict[str, Counter] = defaultdict(Counter)
        # Global term frequency (for IDF)
        self._global_term_freq: Counter = Counter()
        self._total_messages: int = 0
        # Historical similarity scores for trend detection
        self._similarity_history: List[float] = []

    def record_message(self, agent_id: str, content: str) -> None:
        """Record a message from an agent for semantic analysis."""
        normalized = _normalize_text(content)
        if not normalized:
            return

        self._agent_messages[agent_id].append(normalized)

        # Trim to window
        if len(self._agent_messages[agent_id]) > self._window_size:
            self._agent_messages[agent_id] = self._agent_messages[agent_id][
                -self._window_size :
            ]

        # Update n-gram vectors
        ngrams = _extract_ngrams(normalized, self._ngram_size)
        self._agent_ngrams[agent_id].update(ngrams)

        # Update term vectors
        terms = _extract_terms(normalized)
        self._agent_terms[agent_id].update(terms)

        self._global_term_freq.update(set(terms))
        self._total_messages += 1

    def evaluate(self, team_members: Set[str]) -> SemanticSnapshot:
        """Evaluate semantic convergence risk for a team.

        Args:
            team_members: Set of agent IDs to evaluate.

        Returns:
            SemanticSnapshot with convergence metrics and risk score.
        """
        members_with_data = [
            m for m in team_members if m in self._agent_ngrams
        ]

        if len(members_with_data) < 2:
            return SemanticSnapshot(risk_score=0.0)

        # Pairwise n-gram similarity
        similarities: List[float] = []
        for i in range(len(members_with_data)):
            for j in range(i + 1, len(members_with_data)):
                sim = _cosine_similarity(
                    self._agent_ngrams[members_with_data[i]],
                    self._agent_ngrams[members_with_data[j]],
                )
                similarities.append(sim)

        avg_similarity = (
            sum(similarities) / len(similarities) if similarities else 0.0
        )

        # Vocabulary overlap
        vocab_overlap = self._compute_vocabulary_overlap(members_with_data)

        # Convergence trend
        self._similarity_history.append(avg_similarity)
        trend = self._compute_trend()

        # Specialized terms (high TF-IDF within team, rare globally)
        specialized = self._find_specialized_terms(members_with_data)

        # Risk score
        risk_score = _compute_semantic_risk(
            avg_similarity=avg_similarity,
            vocab_overlap=vocab_overlap,
            convergence_trend=trend,
            n_specialized=len(specialized),
        )

        return SemanticSnapshot(
            avg_pairwise_similarity=avg_similarity,
            vocabulary_overlap=vocab_overlap,
            convergence_trend=trend,
            specialized_terms=specialized[:10],
            risk_score=max(0.0, min(1.0, risk_score)),
        )

    def _compute_vocabulary_overlap(self, members: List[str]) -> float:
        """Compute Jaccard similarity of vocabulary across members."""
        if len(members) < 2:
            return 0.0

        vocabularies = [set(self._agent_terms[m].keys()) for m in members]

        intersection = vocabularies[0]
        union = vocabularies[0]
        for v in vocabularies[1:]:
            intersection = intersection & v
            union = union | v

        return len(intersection) / len(union) if union else 0.0

    def _compute_trend(self) -> float:
        """Compute convergence trend from similarity history.

        Returns positive value if converging, negative if diverging.
        """
        history = self._similarity_history[-10:]
        if len(history) < 3:
            return 0.0

        # Simple linear regression slope
        n = len(history)
        x_mean = (n - 1) / 2.0
        y_mean = sum(history) / n

        numerator = sum(
            (i - x_mean) * (history[i] - y_mean) for i in range(n)
        )
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        return numerator / denominator if denominator > 0 else 0.0

    def _find_specialized_terms(
        self, members: List[str], top_k: int = 10
    ) -> List[str]:
        """Find terms that are specialized within the team.

        Terms with high TF within team but low global frequency.
        """
        if self._total_messages < 2:
            return []

        team_terms: Counter = Counter()
        for m in members:
            team_terms.update(self._agent_terms[m])

        scored: List[Tuple[str, float]] = []
        for term, tf in team_terms.items():
            df = self._global_term_freq.get(term, 1)
            idf = math.log(self._total_messages / df) if df > 0 else 0
            tfidf = tf * idf
            # Boost terms shared across multiple team members
            member_count = sum(
                1 for m in members if term in self._agent_terms[m]
            )
            if member_count >= 2:
                scored.append((term, tfidf * member_count))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [term for term, _ in scored[:top_k]]

    def clear(self) -> None:
        """Reset all tracked state."""
        self._agent_messages.clear()
        self._agent_ngrams.clear()
        self._agent_terms.clear()
        self._global_term_freq.clear()
        self._total_messages = 0
        self._similarity_history.clear()


def _normalize_text(text: str) -> str:
    """Normalize text for analysis."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_ngrams(text: str, n: int) -> List[str]:
    """Extract character n-grams from text."""
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def _extract_terms(text: str) -> List[str]:
    """Extract word terms from text."""
    return [w for w in text.split() if len(w) >= 2]


def _cosine_similarity(a: Counter, b: Counter) -> float:
    """Compute cosine similarity between two Counter vectors."""
    if not a or not b:
        return 0.0

    common_keys = set(a.keys()) & set(b.keys())
    if not common_keys:
        return 0.0

    dot_product = sum(a[k] * b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def _compute_semantic_risk(
    avg_similarity: float,
    vocab_overlap: float,
    convergence_trend: float,
    n_specialized: int,
) -> float:
    """Compute composite semantic risk score in [0, 1]."""
    risk = 0.0

    # High similarity is suspicious
    if avg_similarity > 0.8:
        risk += 0.35
    elif avg_similarity > 0.6:
        risk += 0.2
    elif avg_similarity > 0.4:
        risk += 0.1

    # High vocabulary overlap
    if vocab_overlap > 0.7:
        risk += 0.25
    elif vocab_overlap > 0.4:
        risk += 0.1

    # Strong convergence trend
    if convergence_trend > 0.1:
        risk += 0.2
    elif convergence_trend > 0.05:
        risk += 0.1

    # Specialized vocabulary development
    if n_specialized > 5:
        risk += 0.2
    elif n_specialized > 2:
        risk += 0.1

    return max(0.0, min(1.0, risk))
