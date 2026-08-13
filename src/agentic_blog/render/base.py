"""Shared rendering helpers and the front-matter/slug utilities.

Renderers are thin: they select a slice of ``Knowledge`` and shape it per their
``RenderPolicy``. Common Markdown-building helpers live here to keep each
renderer focused on *what to include*, not string plumbing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from agentic_blog.contracts import Framework, Knowledge, Section, Term


def slugify(text: str, *, max_length: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:max_length].strip("-") or "untitled"


def approx_words(text: str) -> int:
    return len(text.split())


def approx_tokens(text: str) -> int:
    """Rough token estimate (~1.33 tokens per word) for budget enforcement."""
    return round(approx_words(text) / 0.75)


def tokens_to_words(tokens: int) -> int:
    """Word budget that fits within ``tokens`` (inverse of :func:`approx_tokens`)."""
    return int(tokens * 0.75)


def provenance_front_matter(knowledge: Knowledge) -> list[str]:
    """YAML front-matter lines carrying render provenance (research-os convention).

    Emits ``created`` (ISO date, from ``metadata['created']``) and a ``sources``
    list (from ``provenance``). Returns ``[]`` when neither is present so callers
    can keep their original output unchanged.
    """
    created = knowledge.metadata.get("created")
    sources = list(knowledge.provenance)
    if not created and not sources:
        return []
    lines: list[str] = []
    if created:
        lines.append(f"created: {created}")
    if sources:
        lines.append("sources:")
        lines += [f"  - {src}" for src in sources]
    return lines


def trim_to_words(text: str, limit: int) -> str:
    """Trim prose to roughly ``limit`` words on a sentence-ish boundary."""
    words = text.split()
    if len(words) <= limit:
        return text
    clipped = " ".join(words[:limit])
    tail = re.search(r"[.!?][^.!?]*$", clipped)
    if tail and tail.start() > len(clipped) * 0.5:
        return clipped[: tail.start() + 1]
    return clipped + "…"


def bullet_list(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def render_frameworks(frameworks: Sequence[Framework]) -> str:
    blocks: list[str] = []
    for fw in frameworks:
        lines = [f"### {fw.name}", "", fw.summary]
        if fw.when_to_use:
            lines += ["", f"**When to use:** {fw.when_to_use}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_glossary(terms: Sequence[Term]) -> str:
    return "\n".join(f"- **{t.name}** — {t.definition}" for t in terms)


def render_section(section: Section, *, heading_level: int = 2) -> str:
    hashes = "#" * heading_level
    parts = [f"{hashes} {section.title}".rstrip(), "", section.body]
    if section.takeaways:
        parts += ["", "**Takeaways:**", bullet_list(section.takeaways)]
    return "\n".join(parts)
