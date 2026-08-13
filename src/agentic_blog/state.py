"""``PipelineState`` — the TypedDict threaded through the LangGraph nodes.

Kept flat and JSON-ish so the SQLite checkpointer can serialize it for resumable
runs. Rich value objects (RawDocument, Knowledge, Artifact) are carried as-is;
LangGraph's checkpointer pickles them.
"""

from __future__ import annotations

from typing import TypedDict

from agentic_blog.contracts import Artifact, Knowledge, MemoryContext, RawDocument


class PipelineState(TypedDict, total=False):
    # inputs
    topic: str
    sources: list[str]
    renders: list[str]
    run_date: str
    reextract: bool  # force re-extraction, bypassing the ingest cache

    # ingest
    documents: list[RawDocument]
    ingest_failures: list[str]

    # memory (read)
    memory_context: MemoryContext
    novel_documents: list[RawDocument]

    # distill
    knowledge: Knowledge
    score: float
    iterations: int
    approved: bool
    critique: str

    # render
    artifacts: list[Artifact]
