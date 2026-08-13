"""Knowledge-base :class:`MemoryStore` — a stub for a future vector/graph backend.

Kept intentionally minimal to prove the seam: the rest of the system depends only
on the ``MemoryStore`` Protocol, so a real RAG/vector implementation can drop in
here without touching any other silo. Selecting it today raises a clear error.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from agentic_blog.contracts import MemoryContext, RunRecord


class KnowledgeBaseStore:
    """Placeholder KB backend. Implements the ``MemoryStore`` Protocol shape."""

    def __init__(self, root: Path, **_: object) -> None:
        self._root = Path(root)

    def context_for(self, topic: str, source_ids: Sequence[str]) -> MemoryContext:
        raise NotImplementedError(
            "KnowledgeBaseStore is a stub. Set memory.backend: markdown in config, "
            "or implement a vector/graph backend behind this Protocol."
        )

    def already_ingested(self, topic: str, source_id: str) -> bool:
        raise NotImplementedError("KnowledgeBaseStore is a stub.")

    def record(self, run: RunRecord) -> None:
        raise NotImplementedError("KnowledgeBaseStore is a stub.")
