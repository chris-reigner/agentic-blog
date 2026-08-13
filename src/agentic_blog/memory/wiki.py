"""``Memory`` — the façade every silo talks to, plus backend construction.

The graph and distiller depend on this thin façade and the ``MemoryStore``
Protocol, never on a concrete store. ``build_store`` is the single place that
maps ``memory.backend`` config to a concretion (Markdown today, KB later).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from agentic_blog.contracts import (
    MemoryContext,
    MemoryEntry,
    MemoryStore,
    RawDocument,
    RunRecord,
)
from agentic_blog.memory.kb_store import KnowledgeBaseStore
from agentic_blog.memory.markdown_store import MarkdownStore
from agentic_blog.memory.models import keywords_from_text
from agentic_blog.settings import MemorySettings

logger = logging.getLogger(__name__)


def build_store(settings: MemorySettings, root: Path, *, today: str) -> MemoryStore:
    """Construct the configured backend (the Markdown↔KB swap point)."""
    if settings.backend == "markdown":
        return MarkdownStore(
            root,
            novelty_window_days=settings.novelty_window_days,
            max_lessons_injected=settings.max_lessons_injected,
            today=today,
        )
    if settings.backend == "knowledge_base":
        return KnowledgeBaseStore(root)
    raise ValueError(f"Unknown memory backend: {settings.backend!r}")


class Memory:
    """Read/write façade over any ``MemoryStore``."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def context_for(self, topic: str, documents: Sequence[RawDocument]) -> MemoryContext:
        """Structured memory to inject into distillation for ``topic``."""
        logger.info("Reading memory for topic %r", topic)
        return self._store.context_for(topic, [d.source_id for d in documents])

    def novel_documents(
        self, topic: str, documents: Sequence[RawDocument]
    ) -> tuple[list[RawDocument], list[RawDocument]]:
        """Split documents into (novel, already-ingested) for this topic."""
        novel: list[RawDocument] = []
        seen: list[RawDocument] = []
        for doc in documents:
            (seen if self._store.already_ingested(topic, doc.source_id) else novel).append(doc)
        return novel, seen

    def record(
        self,
        topic: str,
        *,
        title: str,
        documents: Sequence[RawDocument],
        score: float,
        iterations: int,
        critique: str,
        run_date: str = "",
    ) -> None:
        """Persist a completed run: one memory entry per source, plus lessons/log."""
        entries = [
            MemoryEntry(
                source_id=doc.source_id,
                title=doc.title or title,
                added=run_date,
                score=score,
                iterations=iterations,
                keywords=keywords_from_text(doc.title or title, doc.text),
                origin=doc.origin,
            )
            for doc in documents
        ]
        self._store.record(
            RunRecord(
                topic=topic,
                title=title,
                sources=entries,
                score=score,
                iterations=iterations,
                critique=critique,
                run_date=run_date,
            )
        )
        logger.info("Recorded run for topic %r (%d source(s))", topic, len(entries))
