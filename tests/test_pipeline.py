"""End-to-end: ingest → memory → distill → render → memory.write, with a fake LLM."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from agentic_blog.contracts import Knowledge
from agentic_blog.pipeline import Pipeline
from agentic_blog.settings import PipelineSettings, RenderSettings, Settings
from tests.conftest import FakeLLM


def _settings(output_root: Path) -> Settings:
    settings = Settings(render=RenderSettings(kinds=["markdown"]))
    settings.pipeline = PipelineSettings(output_root=output_root)
    return settings


def _write_distilled(out: Path, topic: str, knowledge: Knowledge) -> None:
    dest = out / topic / "distilled"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "knowledge.json").write_text(
        json.dumps(dataclasses.asdict(knowledge), ensure_ascii=False), encoding="utf-8"
    )


def test_pipeline_run_produces_artifacts_and_memory(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("# Observability\n" + "Metrics, logs, traces. " * 50, encoding="utf-8")
    out = tmp_path / "out"

    pipe = Pipeline(_settings(out), llm=FakeLLM(score=8.5), today="2026-07-29")
    result = pipe.run(topic="observability", sources=[str(source)], renders=["markdown", "skill"])

    assert result.approved
    assert set(result.artifacts) == {"markdown", "skill"}
    topic_dir = out / "observability"
    assert (topic_dir / "artifacts" / "skill" / "SKILL.md").exists()
    assert (topic_dir / "artifacts" / "markdown").exists()
    # memory recorded
    assert (topic_dir / "index.yaml").exists()
    assert (topic_dir / "entries").exists()


def test_rerun_dedups_but_still_renders(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("Metrics, logs, traces. " * 50, encoding="utf-8")
    out = tmp_path / "out"
    pipe = Pipeline(_settings(out), llm=FakeLLM(score=8.5), today="2026-07-29")

    pipe.run(topic="observability", sources=[str(source)], renders=["markdown"])
    result = pipe.run(topic="observability", sources=[str(source)], renders=["markdown"])
    # second run still yields an artifact even though the source was already ingested
    assert "markdown" in result.artifacts


def test_bad_source_is_skipped_not_fatal(tmp_path: Path) -> None:
    good = tmp_path / "notes.md"
    good.write_text("Metrics, logs, traces. " * 50, encoding="utf-8")
    out = tmp_path / "out"
    pipe = Pipeline(_settings(out), llm=FakeLLM(score=8.5), today="2026-07-29")

    result = pipe.run(topic="obs", sources=[str(good), "missing.zzz"], renders=["markdown"])
    assert result.ingest_failures
    assert "markdown" in result.artifacts


def test_render_from_distilled(tmp_path: Path, knowledge: Knowledge) -> None:
    out = tmp_path / "out"
    _write_distilled(out, "obs", knowledge)
    pipe = Pipeline(_settings(out), llm=FakeLLM(), today="2026-07-29")

    result = pipe.render(topic="obs", renders=["markdown", "skill"])

    assert set(result.artifacts) == {"markdown", "skill"}
    topic_dir = out / "obs"
    assert (topic_dir / "artifacts" / "skill" / "SKILL.md").exists()
    assert all(status == "created" for _, status in result.statuses)
    # Provenance + injected created date land in the rendered markdown front-matter.
    md = next(iter(result.artifacts["markdown"].files.values()))
    assert "created: 2026-07-29" in md
    assert knowledge.provenance[0] in md
    # Render log written and dated.
    log = topic_dir / "artifacts" / "log.md"
    assert log.exists()
    assert "[2026-07-29] render | obs | markdown, skill" in log.read_text(encoding="utf-8")


def test_render_rerun_reports_unchanged(tmp_path: Path, knowledge: Knowledge) -> None:
    out = tmp_path / "out"
    _write_distilled(out, "obs", knowledge)
    pipe = Pipeline(_settings(out), llm=FakeLLM(), today="2026-07-29")

    pipe.render(topic="obs", renders=["markdown"])
    result = pipe.render(topic="obs", renders=["markdown"])
    assert all(status == "unchanged" for _, status in result.statuses)


def test_render_without_distilled_raises(tmp_path: Path) -> None:
    pipe = Pipeline(_settings(tmp_path / "out"), llm=FakeLLM(), today="2026-07-29")
    with pytest.raises(FileNotFoundError, match="Run `distill` first"):
        pipe.render(topic="obs", renders=["markdown"])
