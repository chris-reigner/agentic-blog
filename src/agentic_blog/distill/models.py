"""Builders that turn parsed LLM JSON into the ``Knowledge`` value object.

Keeping construction here (not in the LLM node) means the JSON schema and the
frozen contract are validated in one small, testable place.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from agentic_blog.contracts import Framework, Knowledge, Section, Term


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def section_from_dict(data: Mapping[str, Any]) -> Section:
    return Section(
        title=_as_str(data.get("title")),
        body=_as_str(data.get("body")),
        takeaways=tuple(_as_str_list(data.get("takeaways"))),
    )


def framework_from_dict(data: Mapping[str, Any]) -> Framework:
    return Framework(
        name=_as_str(data.get("name")),
        summary=_as_str(data.get("summary")),
        when_to_use=_as_str(data.get("when_to_use")),
    )


def term_from_dict(data: Mapping[str, Any]) -> Term:
    return Term(name=_as_str(data.get("name")), definition=_as_str(data.get("definition")))


def knowledge_from_dict(
    data: Mapping[str, Any],
    *,
    provenance: Sequence[str] = (),
    metadata: Mapping[str, object] | None = None,
) -> Knowledge:
    """Assemble a ``Knowledge`` from a distiller's JSON payload."""
    sections = [section_from_dict(s) for s in data.get("sections", []) if isinstance(s, dict)]
    frameworks = [framework_from_dict(f) for f in data.get("frameworks", []) if isinstance(f, dict)]
    terms = [term_from_dict(t) for t in data.get("key_terms", []) if isinstance(t, dict)]
    return Knowledge(
        title=_as_str(data.get("title")) or "Untitled",
        summary=_as_str(data.get("summary")),
        sections=tuple(s for s in sections if s.title or s.body),
        frameworks=tuple(f for f in frameworks if f.name),
        key_terms=tuple(t for t in terms if t.name),
        takeaways=tuple(_as_str_list(data.get("takeaways"))),
        provenance=tuple(provenance),
        metadata=dict(metadata or {}),
    )


def knowledge_to_dict(knowledge: Knowledge) -> dict[str, Any]:
    """Serialize a ``Knowledge`` to the distiller JSON shape (for critic/writer)."""
    return {
        "title": knowledge.title,
        "summary": knowledge.summary,
        "frameworks": [
            {"name": f.name, "summary": f.summary, "when_to_use": f.when_to_use}
            for f in knowledge.frameworks
        ],
        "key_terms": [{"name": t.name, "definition": t.definition} for t in knowledge.key_terms],
        "sections": [
            {"title": s.title, "body": s.body, "takeaways": list(s.takeaways)}
            for s in knowledge.sections
        ],
        "takeaways": list(knowledge.takeaways),
    }


def knowledge_to_json(knowledge: Knowledge) -> str:
    return json.dumps(knowledge_to_dict(knowledge), ensure_ascii=False, indent=2)
