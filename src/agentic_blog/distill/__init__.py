"""Distill silo: RawDocument(s) + memory context → render-agnostic ``Knowledge``.

Critique happens **once** here (single critic, or an optional debate panel), on
the shared ``Knowledge`` — never per rendered artifact. Nothing in this silo
knows what the final artifact will be.
"""

from __future__ import annotations

from agentic_blog.distill.critic import Critic, Critique
from agentic_blog.distill.debate import DebatePanel
from agentic_blog.distill.distiller import Distiller
from agentic_blog.distill.service import DistillResult, DistillService
from agentic_blog.distill.writer import Writer

__all__ = [
    "Critic",
    "Critique",
    "DebatePanel",
    "DistillResult",
    "DistillService",
    "Distiller",
    "Writer",
]
