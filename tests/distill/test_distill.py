"""Distill silo: JSON→Knowledge, single critique loop, debate path."""

from __future__ import annotations

from agentic_blog.contracts import RawDocument
from agentic_blog.distill.models import knowledge_from_dict, knowledge_to_dict
from agentic_blog.distill.service import DistillService
from agentic_blog.llm import extract_json
from agentic_blog.settings import DebateSettings, PipelineSettings
from tests.conftest import FakeLLM


def _doc() -> RawDocument:
    return RawDocument(
        source_id="a", origin="/a.pdf", mime="application/pdf", text="content " * 50, title="A"
    )


def test_knowledge_roundtrip() -> None:
    payload = {
        "title": "T",
        "summary": "S",
        "frameworks": [{"name": "F", "summary": "x", "when_to_use": "y"}],
        "key_terms": [{"name": "K", "definition": "d"}],
        "sections": [{"title": "Sec", "body": "b", "takeaways": ["t"]}],
        "takeaways": ["big"],
    }
    knowledge = knowledge_from_dict(payload)
    assert knowledge.title == "T"
    assert knowledge_to_dict(knowledge)["frameworks"][0]["name"] == "F"


def test_extract_json_tolerates_fences() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prose before {"a": 2} after') == {"a": 2}


def test_distill_approves_on_high_score() -> None:
    svc = DistillService(
        FakeLLM(score=9.0),
        pipeline=PipelineSettings(max_critique_iterations=3, approval_threshold=7),
        debate=DebateSettings(enabled=False),
    )
    result = svc.run("observability", [_doc()])
    assert result.approved
    assert result.iterations == 1
    assert result.knowledge.frameworks


def test_distill_loops_until_max_when_rejected() -> None:
    svc = DistillService(
        FakeLLM(score=3.0),
        pipeline=PipelineSettings(max_critique_iterations=3, approval_threshold=7),
        debate=DebateSettings(enabled=False),
    )
    result = svc.run("observability", [_doc()])
    assert not result.approved
    assert result.iterations == 3


def test_debate_panel_path() -> None:
    svc = DistillService(
        FakeLLM(score=8.0),
        pipeline=PipelineSettings(max_critique_iterations=2, approval_threshold=7),
        debate=DebateSettings(enabled=True, num_personas=3),
    )
    result = svc.run("observability", [_doc()])
    assert result.approved
    assert result.score == 8.0
