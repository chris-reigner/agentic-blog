"""Markdown renderer: full long-form prose (low compression)."""

from __future__ import annotations

from agentic_blog.contracts import Artifact, Knowledge
from agentic_blog.render.base import (
    provenance_front_matter,
    render_frameworks,
    render_glossary,
    render_section,
    slugify,
)
from agentic_blog.settings import RenderPolicy


class MarkdownRenderer:
    kind = "markdown"

    def __init__(self, policy: RenderPolicy) -> None:
        self._policy = policy

    def render(self, knowledge: Knowledge) -> Artifact:
        parts: list[str] = []
        front_matter = provenance_front_matter(knowledge)
        if front_matter:
            parts += ["---", *front_matter, "---", ""]
        parts += [f"# {knowledge.title}", "", knowledge.summary]
        if knowledge.takeaways:
            parts += ["", "## Key takeaways", ""]
            parts += [f"- {t}" for t in knowledge.takeaways]
        if knowledge.frameworks:
            parts += ["", "## Frameworks", "", render_frameworks(knowledge.frameworks)]
        for section in knowledge.sections:
            parts += ["", render_section(section)]
        if knowledge.key_terms:
            parts += ["", "## Glossary", "", render_glossary(knowledge.key_terms)]
        if knowledge.provenance:
            parts += ["", "## Sources", ""]
            parts += [f"- {src}" for src in knowledge.provenance]
        content = "\n".join(parts) + "\n"
        return Artifact(
            kind=self.kind,
            files={f"{slugify(knowledge.title)}.md": content},
            summary=knowledge.summary,
        )
