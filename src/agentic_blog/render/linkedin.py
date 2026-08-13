"""LinkedIn renderer: hook + 3 points + hashtags (high compression)."""

from __future__ import annotations

from agentic_blog.contracts import Artifact, Knowledge
from agentic_blog.render.base import slugify, trim_to_words
from agentic_blog.settings import RenderPolicy


class LinkedInRenderer:
    kind = "linkedin"

    def __init__(self, policy: RenderPolicy) -> None:
        self._policy = policy

    def _hashtags(self, knowledge: Knowledge) -> str:
        count = self._policy.hashtags or 3
        tags = [
            "#" + "".join(word.capitalize() for word in term.name.split())
            for term in knowledge.key_terms[:count]
        ]
        return " ".join(tags)

    def render(self, knowledge: Knowledge) -> Artifact:
        hook = trim_to_words(knowledge.summary, 30)
        points = list(knowledge.takeaways[:3]) or [s.title for s in knowledge.sections[:3]]
        lines = [hook, ""]
        for point in points:
            lines.append(f"→ {point}")
        hashtags = self._hashtags(knowledge)
        if hashtags:
            lines += ["", hashtags]
        content = "\n".join(lines) + "\n"
        return Artifact(
            kind=self.kind,
            files={f"{slugify(knowledge.title)}-linkedin.md": content},
            summary=hook,
        )
