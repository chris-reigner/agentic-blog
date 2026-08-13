"""Render silo: one shared ``Knowledge`` → many ``Artifact``s.

"A skill is just a renderer." Every renderer consumes the *same* ``Knowledge``
and differs only in which fields it reads and how hard it compresses. Adding a
format is registering a renderer (Open/Closed) — the pipeline never changes.
"""

from __future__ import annotations

from agentic_blog.render.blog import BlogRenderer
from agentic_blog.render.linkedin import LinkedInRenderer
from agentic_blog.render.markdown import MarkdownRenderer
from agentic_blog.render.registry import (
    DEFAULT_KINDS,
    RenderRegistry,
    available_kinds,
)
from agentic_blog.render.service import RenderService
from agentic_blog.render.skill import SkillRenderer

__all__ = [
    "DEFAULT_KINDS",
    "BlogRenderer",
    "LinkedInRenderer",
    "MarkdownRenderer",
    "RenderRegistry",
    "RenderService",
    "SkillRenderer",
    "available_kinds",
]
