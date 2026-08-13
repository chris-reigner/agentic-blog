"""Simplified LangGraph orchestration wiring the four silos together.

Linear flow (the critique loop is internal to the distill node, per the locked
design decision that critique happens once on shared Knowledge):

    ingest → memory.read → distill → render → memory.write → END

A SQLite checkpointer is attached when available so runs are resumable by
``thread_id``. The nodes are thin adapters; all real work lives in the silos.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_blog.distill.service import DistillService
from agentic_blog.ingest import cache
from agentic_blog.ingest.raw_store import RawStore
from agentic_blog.ingest.service import IngestService
from agentic_blog.memory.wiki import Memory
from agentic_blog.render.service import RenderService
from agentic_blog.state import PipelineState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Silos:
    """The four silo services a run needs, injected into the graph nodes."""

    ingest: IngestService
    memory: Memory
    distill: DistillService
    render: RenderService
    raw_store: RawStore | None = None


def _ingest_node(silos: Silos) -> Callable[[PipelineState], dict[str, Any]]:
    def run(state: PipelineState) -> dict[str, Any]:
        sources = list(state.get("sources", []))
        if silos.raw_store is not None:
            resolved = cache.resolve(
                silos.ingest,
                silos.raw_store,
                state["topic"],
                sources,
                reextract=state.get("reextract", False),
            )
            documents, failures = resolved.documents, resolved.failures
        else:
            result = silos.ingest.load(sources)
            documents, failures = result.documents, result.failures
        return {
            "documents": documents,
            "ingest_failures": [f"{f.origin}: {f.reason}" for f in failures],
        }

    return run


def _memory_read_node(silos: Silos) -> Callable[[PipelineState], dict[str, Any]]:
    def run(state: PipelineState) -> dict[str, Any]:
        topic = state["topic"]
        documents = state.get("documents", [])
        novel, _seen = silos.memory.novel_documents(topic, documents)
        context = silos.memory.context_for(topic, documents)
        # Fall back to all documents if everything was already ingested, so a
        # re-run still produces artifacts.
        return {"novel_documents": novel or list(documents), "memory_context": context}

    return run


def _distill_node(silos: Silos) -> Callable[[PipelineState], dict[str, Any]]:
    def run(state: PipelineState) -> dict[str, Any]:
        result = silos.distill.run(
            state["topic"],
            state.get("novel_documents", state.get("documents", [])),
            state.get("memory_context"),
        )
        return {
            "knowledge": result.knowledge,
            "score": result.score,
            "iterations": result.iterations,
            "approved": result.approved,
            "critique": result.critique,
        }

    return run


def _render_node(silos: Silos) -> Callable[[PipelineState], dict[str, Any]]:
    def run(state: PipelineState) -> dict[str, Any]:
        artifacts = silos.render.render(state["knowledge"], state.get("renders", ["markdown"]))
        return {"artifacts": artifacts}

    return run


def _memory_write_node(silos: Silos) -> Callable[[PipelineState], dict[str, Any]]:
    def run(state: PipelineState) -> dict[str, Any]:
        knowledge = state["knowledge"]
        silos.memory.record(
            state["topic"],
            title=knowledge.title,
            documents=state.get("documents", []),
            score=state.get("score", 0.0),
            iterations=state.get("iterations", 0),
            critique=state.get("critique", ""),
            run_date=state.get("run_date", ""),
        )
        return {}

    return run


def build_graph(silos: Silos, *, checkpoint_path: Path | None = None) -> Any:
    """Compile the LangGraph. Falls back to a plain runner if LangGraph is absent."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:  # pragma: no cover - langgraph declared in pyproject
        return _LinearRunner(silos)

    # Typed as Any: LangGraph's add_node overloads don't accept a plain
    # ``Callable[[State], dict]`` under mypy --strict, but that is exactly the
    # thin-adapter shape we use. The node functions are individually typed.
    graph: Any = StateGraph(PipelineState)
    graph.add_node("ingest", _ingest_node(silos))
    graph.add_node("memory_read", _memory_read_node(silos))
    graph.add_node("distill", _distill_node(silos))
    graph.add_node("render", _render_node(silos))
    graph.add_node("memory_write", _memory_write_node(silos))

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "memory_read")
    graph.add_edge("memory_read", "distill")
    graph.add_edge("distill", "render")
    graph.add_edge("render", "memory_write")
    graph.add_edge("memory_write", END)

    checkpointer = _build_checkpointer(checkpoint_path)
    return graph.compile(checkpointer=checkpointer)


def _build_checkpointer(checkpoint_path: Path | None) -> Any:
    if checkpoint_path is None:
        return None
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:  # pragma: no cover
        logger.info("langgraph-checkpoint-sqlite not installed; running without checkpoints.")
        return None
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    return SqliteSaver(conn, serde=_serde())


def _serde() -> Any:
    """Serializer that allow-lists our contract value objects for checkpointing.

    Without an explicit allow-list LangGraph warns on every deserialized custom
    type and will block them outright in a future release.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    from agentic_blog import contracts

    allowed = [
        (contracts.__name__, name)
        for name in (
            "RawDocument",
            "Term",
            "Framework",
            "Section",
            "Knowledge",
            "Artifact",
            "MemoryEntry",
            "MemoryContext",
            "RunRecord",
        )
    ]
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)


class _LinearRunner:
    """Dependency-free fallback with the same ``invoke`` surface as a compiled graph."""

    def __init__(self, silos: Silos) -> None:
        self._nodes = [
            _ingest_node(silos),
            _memory_read_node(silos),
            _distill_node(silos),
            _render_node(silos),
            _memory_write_node(silos),
        ]

    def invoke(self, state: PipelineState, config: dict[str, Any] | None = None) -> PipelineState:
        current: dict[str, Any] = dict(state)
        for node in self._nodes:
            current.update(node(current))  # type: ignore[arg-type]
        return current  # type: ignore[return-value]
