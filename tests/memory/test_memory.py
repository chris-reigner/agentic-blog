"""Memory silo: round-trip, dedup, lessons, novelty context."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentic_blog.contracts import RawDocument
from agentic_blog.memory.markdown_store import MarkdownStore
from agentic_blog.memory.wiki import Memory, build_store
from agentic_blog.settings import MemorySettings


def _doc(source_id: str = "obs-1", title: str = "Observability") -> RawDocument:
    return RawDocument(
        source_id=source_id,
        origin=f"/x/{source_id}.pdf",
        mime="application/pdf",
        text="observability metrics logs traces " * 20,
        title=title,
    )


def _memory(tmp_path: Path) -> Memory:
    return Memory(MarkdownStore(tmp_path, today="2026-07-29"))


def test_record_writes_per_topic_layout(tmp_path: Path) -> None:
    mem = _memory(tmp_path)
    mem.record(
        "observability",
        title="Obs skill",
        documents=[_doc()],
        score=8.0,
        iterations=1,
        critique="",
        run_date="2026-07-29",
    )
    topic = tmp_path / "observability"
    assert (topic / "index.yaml").exists()
    assert (topic / "index.md").exists()
    assert (topic / "log.md").exists()
    assert (topic / "entries" / "obs-1.md").exists()
    data = yaml.safe_load((topic / "index.yaml").read_text())
    assert data["entries"][0]["source_id"] == "obs-1"


def test_dedup_by_source_id(tmp_path: Path) -> None:
    mem = _memory(tmp_path)
    docs = [_doc()]
    novel, seen = mem.novel_documents("observability", docs)
    assert len(novel) == 1 and not seen
    mem.record(
        "observability",
        title="t",
        documents=docs,
        score=8,
        iterations=1,
        critique="",
        run_date="2026-07-29",
    )
    novel2, seen2 = mem.novel_documents("observability", docs)
    assert not novel2 and len(seen2) == 1


def test_lessons_recorded_after_hard_run(tmp_path: Path) -> None:
    mem = _memory(tmp_path)
    mem.record(
        "observability",
        title="t",
        documents=[_doc()],
        score=6.0,
        iterations=2,  # >= threshold triggers a lesson
        critique="Tighten the intro.",
        run_date="2026-07-29",
    )
    ctx = mem.context_for("observability", [_doc("new")])
    assert any("Tighten the intro" in lesson for lesson in ctx.lessons)


def test_no_lesson_for_easy_run(tmp_path: Path) -> None:
    mem = _memory(tmp_path)
    mem.record(
        "observability",
        title="t",
        documents=[_doc()],
        score=9,
        iterations=1,
        critique="n/a",
        run_date="2026-07-29",
    )
    assert not (tmp_path / "observability" / "lessons.md").exists()


def test_build_store_selects_markdown() -> None:
    store = build_store(MemorySettings(backend="markdown"), Path("."), today="2026-07-29")
    assert isinstance(store, MarkdownStore)


def test_context_empty_for_new_topic(tmp_path: Path) -> None:
    ctx = _memory(tmp_path).context_for("brand-new", [_doc()])
    assert ctx.is_empty()
    assert ctx.as_prompt_block() == ""
