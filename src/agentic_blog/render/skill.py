"""Skill renderer: a Claude-style skill bundle (structural compression).

"A skill is just another renderer." It consumes the same ``Knowledge`` as every
other renderer but emits a progressive-disclosure bundle:

    SKILL.md        # front-loaded overview + when-to-use + framework index
    chapters/*.md   # one detailed page per section (loaded on demand)
    glossary.md     # key terms
    cheatsheet.md   # the takeaways, dense

The SKILL.md is kept lean (front-matter budget) so an agent loads it cheaply and
pulls chapters only when needed.
"""

from __future__ import annotations

from agentic_blog.contracts import Artifact, Knowledge, Section
from agentic_blog.render.base import (
    approx_tokens,
    approx_words,
    bullet_list,
    provenance_front_matter,
    render_glossary,
    render_section,
    slugify,
    tokens_to_words,
    trim_to_words,
)
from agentic_blog.settings import RenderPolicy


class SkillRenderer:
    kind = "skill"

    def __init__(self, policy: RenderPolicy) -> None:
        self._policy = policy

    def render(self, knowledge: Knowledge) -> Artifact:
        files: dict[str, str] = {}
        chapter_links: list[str] = []

        for index, section in enumerate(knowledge.sections, start=1):
            slug = f"{index:02d}-{slugify(section.title)}"
            files[f"chapters/{slug}.md"] = (
                render_section(self._budget_section(section), heading_level=1) + "\n"
            )
            chapter_links.append(f"- [{section.title}](chapters/{slug}.md)")

        if knowledge.key_terms:
            files["glossary.md"] = "# Glossary\n\n" + render_glossary(knowledge.key_terms) + "\n"
        if knowledge.takeaways:
            files["cheatsheet.md"] = "# Cheat sheet\n\n" + bullet_list(knowledge.takeaways) + "\n"

        files["SKILL.md"] = self._skill_md(knowledge, chapter_links)
        return Artifact(kind=self.kind, files=files, summary=knowledge.summary)

    def _budget_section(self, section: Section) -> Section:
        """Trim a chapter's body to the configured per-chapter token budget."""
        budget = self._policy.chapter_budget_tokens
        if budget is None:
            return section
        return Section(
            title=section.title,
            body=trim_to_words(section.body, tokens_to_words(budget)),
            takeaways=section.takeaways,
        )

    def _skill_md(self, knowledge: Knowledge, chapter_links: list[str]) -> str:
        name = slugify(knowledge.title)
        front_matter = [
            "---",
            f"name: {name}",
            f'description: "{trim_to_words(knowledge.summary, 30)}"',
            *provenance_front_matter(knowledge),
            "---",
        ]
        body_parts = [
            f"# {knowledge.title}",
            "",
            knowledge.summary,
        ]
        if knowledge.frameworks:
            body_parts += ["", "## Frameworks at a glance", ""]
            for fw in knowledge.frameworks:
                when = f" — _{fw.when_to_use}_" if fw.when_to_use else ""
                body_parts.append(f"- **{fw.name}**: {trim_to_words(fw.summary, 25)}{when}")
        if knowledge.takeaways:
            body_parts += ["", "## Core principles", "", bullet_list(knowledge.takeaways)]
        if chapter_links:
            body_parts += ["", "## Chapters (load on demand)", "", *chapter_links]
        if knowledge.key_terms:
            body_parts += ["", "See `glossary.md` for terminology and `cheatsheet.md` for a recap."]

        body = "\n".join(body_parts)
        budget = self._policy.skill_md_max_tokens
        assembled = "\n".join([*front_matter, "", body])
        if budget is not None and approx_tokens(assembled) > budget:
            # Trim the body so the whole file (front-matter included) fits the budget.
            fm_words = approx_words("\n".join(front_matter))
            body = trim_to_words(body, max(tokens_to_words(budget) - fm_words, 0))
            assembled = "\n".join([*front_matter, "", body])
        return assembled + "\n"
