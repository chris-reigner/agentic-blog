"""Inter-silo data contracts and Protocols.

This module is the *only* thing the four silos (ingest, distill, render, memory)
share. Everything else in each silo is private. Value objects are frozen
dataclasses; the seams between silos are ``typing.Protocol`` classes so
concretions can be swapped at the edges (dependency inversion).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# ── Value objects ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RawDocument:
    """Normalized output of the ingest silo — one per source.

    ``source_id`` is a stable identifier derived from the origin (path or URL);
    it is the dedup key shared with the memory silo.
    """

    source_id: str
    origin: str
    mime: str
    text: str
    title: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Term:
    """A glossary-worthy term with a one-line definition."""

    name: str
    definition: str


@dataclass(frozen=True, slots=True)
class Framework:
    """A named framework/mental model with application guidance."""

    name: str
    summary: str
    when_to_use: str = ""


@dataclass(frozen=True, slots=True)
class Section:
    """An ordered chunk of the distilled knowledge (~ a chapter)."""

    title: str
    body: str
    takeaways: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class Knowledge:
    """Render-agnostic distilled representation, shared by every renderer.

    Renderers differ only in which fields they read and how hard they compress
    them (see the render silo). Nothing here knows about the final artifact.
    """

    title: str
    summary: str
    sections: Sequence[Section] = ()
    frameworks: Sequence[Framework] = ()
    key_terms: Sequence[Term] = ()
    takeaways: Sequence[str] = ()
    provenance: Sequence[str] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Artifact:
    """A rendered, consumable output — a bundle of relative-path → content."""

    kind: str
    files: Mapping[str, str]
    summary: str = ""


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """One recorded source within a topic's memory (the per-source dedup unit)."""

    source_id: str
    title: str
    added: str  # ISO date (YYYY-MM-DD)
    score: float = 0.0
    iterations: int = 0
    keywords: Sequence[str] = ()
    origin: str = ""


@dataclass(frozen=True, slots=True)
class MemoryContext:
    """Backend-agnostic memory read, injected into the distiller/writer.

    ``related`` are prior entries on the same topic; ``recent_titles`` are titles
    within the novelty window (to encourage differentiation); ``lessons`` are
    re-injected editorial notes from prior low-scoring runs.
    """

    topic: str
    related: Sequence[MemoryEntry] = ()
    recent_titles: Sequence[str] = ()
    lessons: Sequence[str] = ()

    def is_empty(self) -> bool:
        return not (self.related or self.recent_titles or self.lessons)

    def as_prompt_block(self) -> str:
        """Render this context as a Markdown block for a prompt (empty if nothing)."""
        if self.is_empty():
            return ""
        parts: list[str] = []
        if self.related:
            lines = ["### Previously covered on this topic"]
            lines += [f"- **{e.added}** — {e.title} _(score: {e.score})_" for e in self.related]
            parts.append("\n".join(lines))
        if self.recent_titles:
            lines = ["### Recently written (differentiate the angle)"]
            lines += [f"- {t}" for t in self.recent_titles]
            parts.append("\n".join(lines))
        if self.lessons:
            lines = ["### Editorial lessons — apply without exception"]
            lines += [f"- {ln}" for ln in self.lessons]
            parts.append("\n".join(lines))
        return "\n\n".join(parts)


# ── Protocols (the dependency-inversion seams) ────────────────────────────────


@runtime_checkable
class Parser(Protocol):
    """Turns one source into a :class:`RawDocument`."""

    def can_parse(self, origin: str) -> bool:
        """Return True if this parser handles the given path/URL."""
        ...

    def parse(self, origin: str) -> RawDocument:
        """Extract and normalize one source. Raises on unrecoverable failure."""
        ...


@runtime_checkable
class Renderer(Protocol):
    """Turns one :class:`Knowledge` into one :class:`Artifact`."""

    kind: str

    def render(self, knowledge: Knowledge) -> Artifact:
        """Produce the artifact for this renderer's ``kind``."""
        ...


@dataclass(frozen=True, slots=True)
class RunRecord:
    """The write-path input to the memory silo — one completed run of a topic."""

    topic: str
    title: str
    sources: Sequence[MemoryEntry]
    score: float = 0.0
    iterations: int = 0
    critique: str = ""
    run_date: str = ""  # ISO date; the store fills a default if empty


@runtime_checkable
class MemoryStore(Protocol):
    """Backend seam for the memory silo (Markdown by default, KB later).

    Implementations own all persistence for a topic. Swapping Markdown for a
    knowledge-base backend is a one-line wiring change because every silo depends
    only on this Protocol and the value objects above.
    """

    def context_for(self, topic: str, source_ids: Sequence[str]) -> MemoryContext:
        """Return the structured memory context for a run of ``topic``."""
        ...

    def already_ingested(self, topic: str, source_id: str) -> bool:
        """Return True if this source is already recorded for the topic (dedup)."""
        ...

    def record(self, run: RunRecord) -> None:
        """Persist one run's outcome to the topic's memory (upsert per source)."""
        ...
