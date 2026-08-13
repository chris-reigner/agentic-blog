"""Memory silo: per-topic, Markdown-first knowledge with a pluggable backend.

Read by distillation, informs rendering, written after a run. Every other silo
depends only on the ``MemoryStore`` Protocol (in :mod:`agentic_blog.contracts`)
and the :class:`Memory` façade here — never on a concrete backend.
"""

from __future__ import annotations

from agentic_blog.memory.kb_store import KnowledgeBaseStore
from agentic_blog.memory.markdown_store import MarkdownStore
from agentic_blog.memory.wiki import Memory, build_store

__all__ = [
    "KnowledgeBaseStore",
    "MarkdownStore",
    "Memory",
    "build_store",
]
