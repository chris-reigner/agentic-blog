"""Render silo: all renderers consume the same Knowledge, differ in slice/shape."""

from __future__ import annotations

import dataclasses

import pytest

from agentic_blog.contracts import Knowledge, Section
from agentic_blog.render.base import approx_tokens
from agentic_blog.render.registry import RenderRegistry, available_kinds
from agentic_blog.render.service import RenderService
from agentic_blog.settings import RenderPolicy, RenderSettings


def test_all_kinds_render(knowledge: Knowledge) -> None:
    artifacts = RenderService(RenderSettings(kinds=["markdown"])).render(
        knowledge, ["markdown", "blog", "linkedin", "skill"]
    )
    kinds = {a.kind for a in artifacts}
    assert kinds == {"markdown", "blog", "linkedin", "skill"}


def test_skill_is_progressive_disclosure(knowledge: Knowledge) -> None:
    (skill,) = RenderService(RenderSettings(kinds=["markdown"])).render(knowledge, ["skill"])
    assert "SKILL.md" in skill.files
    assert any(p.startswith("chapters/") for p in skill.files)
    assert "glossary.md" in skill.files
    assert "cheatsheet.md" in skill.files
    assert skill.files["SKILL.md"].startswith("---\nname:")


def test_blog_has_front_matter(knowledge: Knowledge) -> None:
    (blog,) = RenderService(RenderSettings(kinds=["markdown"])).render(knowledge, ["blog"])
    content = next(iter(blog.files.values()))
    assert content.startswith("---")
    assert "title:" in content


def test_linkedin_is_compact(knowledge: Knowledge) -> None:
    (post,) = RenderService(RenderSettings(kinds=["markdown"])).render(knowledge, ["linkedin"])
    content = next(iter(post.files.values()))
    assert "→" in content
    assert "#" in content  # hashtags


def test_provenance_front_matter_on_selected_kinds(knowledge: Knowledge) -> None:
    stamped = dataclasses.replace(knowledge, metadata={"created": "2026-07-29"})
    by_kind = {
        a.kind: a
        for a in RenderService(RenderSettings(kinds=["markdown"])).render(
            stamped, ["markdown", "blog", "skill", "linkedin"]
        )
    }
    contents = {
        "markdown": next(iter(by_kind["markdown"].files.values())),
        "blog": next(iter(by_kind["blog"].files.values())),
        "skill": by_kind["skill"].files["SKILL.md"],
    }
    for content in contents.values():
        assert "created: 2026-07-29" in content
        assert "sources:" in content
        assert knowledge.provenance[0] in content
    # LinkedIn stays paste-able: no front-matter/provenance in the body.
    linkedin = next(iter(by_kind["linkedin"].files.values()))
    assert "created:" not in linkedin
    assert "sources:" not in linkedin


def test_skill_token_budgets_enforced() -> None:
    long_body = "word " * 4000
    big = Knowledge(
        title="Big Topic",
        summary="A summary. " * 50,
        sections=(Section(title="Chapter", body=long_body, takeaways=()),),
        takeaways=tuple(f"principle {i}" for i in range(40)),
    )
    settings = RenderSettings(
        kinds=["skill"],
        skill=RenderPolicy(
            compression="structural", skill_md_max_tokens=50, chapter_budget_tokens=40
        ),
    )
    (skill,) = RenderService(settings).render(big, ["skill"])
    assert approx_tokens(skill.files["SKILL.md"]) <= 50
    (chapter_body,) = (v for k, v in skill.files.items() if k.startswith("chapters/"))
    # Body trimmed to ~30 words; heading/newlines add a little. Far below the 4000-word input.
    assert approx_tokens(chapter_body) < 60

    # Defaults (large budgets) leave the long prose untrimmed.
    (full,) = RenderService(RenderSettings(kinds=["markdown"])).render(big, ["skill"])
    (full_chapter,) = (v for k, v in full.files.items() if k.startswith("chapters/"))
    assert approx_tokens(full_chapter) > 40


def test_unknown_renderer_rejected(knowledge: Knowledge) -> None:
    with pytest.raises(ValueError, match="Unknown renderer"):
        RenderRegistry(RenderSettings(kinds=["markdown"])).build(["nope"])


def test_available_kinds() -> None:
    assert set(available_kinds()) == {"markdown", "blog", "linkedin", "skill"}
