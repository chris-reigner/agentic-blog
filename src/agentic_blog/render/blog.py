"""Blog renderer: narrative post with SEO front-matter (medium compression)."""

from __future__ import annotations

from agentic_blog.contracts import Artifact, Knowledge
from agentic_blog.render.base import (
    approx_words,
    provenance_front_matter,
    render_section,
    slugify,
    trim_to_words,
)
from agentic_blog.settings import RenderPolicy


class BlogRenderer:
    kind = "blog"

    def __init__(self, policy: RenderPolicy) -> None:
        self._policy = policy

    def _front_matter(self, knowledge: Knowledge) -> str:
        keywords = ", ".join(t.name for t in knowledge.key_terms[:6])
        lines = [
            "---",
            f'title: "{knowledge.title}"',
            f'description: "{trim_to_words(knowledge.summary, 30)}"',
        ]
        if self._policy.seo and keywords:
            lines.append(f'keywords: "{keywords}"')
        lines += provenance_front_matter(knowledge)
        lines.append("---")
        return "\n".join(lines)

    def render(self, knowledge: Knowledge) -> Artifact:
        target = self._policy.target_words or 1100
        parts = [self._front_matter(knowledge), "", f"# {knowledge.title}", "", knowledge.summary]

        # Budget the section prose toward the target word count.
        remaining = max(target - approx_words(knowledge.summary), 200)
        top_sections = list(knowledge.sections)
        per_section = max(remaining // max(len(top_sections), 1), 120)
        for section in top_sections:
            trimmed = section.__class__(
                title=section.title,
                body=trim_to_words(section.body, per_section),
                takeaways=section.takeaways[:2],
            )
            parts += ["", render_section(trimmed)]

        if knowledge.takeaways:
            parts += ["", "## Takeaways", ""]
            parts += [f"- {t}" for t in knowledge.takeaways[:5]]

        content = "\n".join(parts) + "\n"
        return Artifact(
            kind=self.kind,
            files={f"{slugify(knowledge.title)}.md": content},
            summary=knowledge.summary,
        )
