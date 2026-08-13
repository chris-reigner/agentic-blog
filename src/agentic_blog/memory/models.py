"""Internal helpers for the memory silo: slugs, keywords, lesson weighting.

Value objects (``MemoryEntry``, ``MemoryContext``, ``RunRecord``) live in
:mod:`agentic_blog.contracts` because they cross silo boundaries. This module
holds only memory-private logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lesson weighting (ported from AgenticBlog): recent lessons matter more.
LESSON_DECAY_FACTOR = 0.85  # applied per new lesson in the same topic
LESSON_PURGE_THRESHOLD = 0.1  # drop a lesson once its weight falls below this

_STOPWORDS = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "have",
        "will",
        "been",
        "long",
        "term",
        "into",
        "over",
        "their",
        "about",
        "after",
        "your",
        "them",
        "then",
        "than",
        "when",
        "what",
        "which",
        "these",
        "those",
        "here",
        "there",
        "such",
        "also",
    }
)


def slugify(text: str, *, max_length: int = 60) -> str:
    """Filesystem- and URL-safe slug: lowercased, hyphen-separated."""
    lowered = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug[:max_length].strip("-") or "untitled"


def keywords_from_text(title: str, body: str, *, limit: int = 8) -> list[str]:
    """Extract salient keywords from a title + body (title-weighted)."""
    text = f"{title} {title} {body[:3000]}".lower()
    words = re.findall(r"[a-z][a-z0-9.\-]{3,}", text)
    counts: dict[str, int] = {}
    for word in words:
        if word in _STOPWORDS:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts, key=lambda w: (counts[w], len(w)), reverse=True)
    return ranked[:limit]


def overlap_ratio(a: set[str], b: set[str]) -> float:
    """Jaccard overlap of two keyword sets (0.0 when either is empty)."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(slots=True)
class Lesson:
    """A weighted editorial lesson recorded after a hard (multi-iteration) run."""

    added: str
    iterations: int
    score: float
    weight: float
    critique: str

    def decayed(self) -> Lesson:
        return Lesson(
            added=self.added,
            iterations=self.iterations,
            score=self.score,
            weight=round(self.weight * LESSON_DECAY_FACTOR, 4),
            critique=self.critique,
        )
