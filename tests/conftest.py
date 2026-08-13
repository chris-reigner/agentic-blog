"""Shared fixtures: a fake LLM and canned Knowledge, so no network is needed."""

from __future__ import annotations

import json

import pytest

from agentic_blog.contracts import Framework, Knowledge, Section, Term


class FakeLLM:
    """Deterministic ``LLMClient`` that returns canned JSON per prompt role."""

    def __init__(self, *, score: float = 8.5, distiller_payload: dict | None = None) -> None:
        self.score = score
        self.calls: list[tuple[str, str]] = []
        self._distiller_payload = distiller_payload or {
            "title": "Observability",
            "summary": "How to build observable systems. " * 3,
            "frameworks": [
                {
                    "name": "Three Pillars",
                    "summary": "metrics/logs/traces",
                    "when_to_use": "telemetry",
                }
            ],
            "key_terms": [{"name": "SLI", "definition": "service level indicator"}],
            "sections": [
                {
                    "title": "Pillars",
                    "body": "detailed body " * 30,
                    "takeaways": ["instrument early"],
                }
            ],
            "takeaways": ["observe from the user", "cardinality matters"],
        }

    def complete(self, system: str, user: str, temperature: float | None = None) -> str:
        self.calls.append((system, user))
        sl = system.lower()
        if "knowledge distiller" in sl:
            return json.dumps(self._distiller_payload)
        if "demanding editor" in sl:
            return json.dumps(
                {"score": self.score, "approved": self.score >= 7, "critique": "solid"}
            )
        if "panel" in sl or "persona" in sl:
            return json.dumps({"score": self.score, "critique": "panel note"})
        if "refining" in sl:
            return json.dumps(self._distiller_payload)
        return "{}"


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def knowledge() -> Knowledge:
    return Knowledge(
        title="Observability Engineering",
        summary="How to build observable systems using the three pillars and SLOs.",
        sections=(
            Section(
                title="Three Pillars",
                body="Metrics, logs, traces." * 10,
                takeaways=("Instrument early",),
            ),
            Section(
                title="SLOs", body="Define objectives." * 10, takeaways=("Pick user-centric SLIs",)
            ),
        ),
        frameworks=(
            Framework(
                name="Three Pillars",
                summary="Metrics, logs, traces",
                when_to_use="telemetry design",
            ),
        ),
        key_terms=(
            Term(name="SLI", definition="Service level indicator"),
            Term(name="SLO", definition="Service level objective"),
        ),
        takeaways=("Observe from the user perspective", "Cardinality matters"),
        provenance=("/x/obs.pdf",),
    )
