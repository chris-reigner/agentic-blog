"""Critic: score a ``Knowledge`` and decide whether it is reusable enough."""

from __future__ import annotations

from dataclasses import dataclass

from agentic_blog.contracts import Knowledge
from agentic_blog.distill.models import knowledge_to_json
from agentic_blog.distill.prompts import CRITIC_SYSTEM, CRITIC_USER
from agentic_blog.llm import LLMClient, extract_json


@dataclass(frozen=True, slots=True)
class Critique:
    """A single critic verdict."""

    score: float
    approved: bool
    critique: str


class Critic:
    """Single-critic quality gate (the default when debate is disabled)."""

    def __init__(self, llm: LLMClient, *, approval_threshold: float) -> None:
        self._llm = llm
        self._threshold = approval_threshold

    def review(self, topic: str, knowledge: Knowledge) -> Critique:
        user = CRITIC_USER.format(topic=topic, knowledge_json=knowledge_to_json(knowledge))
        system = CRITIC_SYSTEM.replace("{threshold}", str(self._threshold))
        data = extract_json(self._llm.complete(system, user))
        if not isinstance(data, dict):
            raise ValueError("Critic expected a JSON object.")
        score = float(data.get("score", 0.0))
        approved = bool(data.get("approved", score >= self._threshold))
        return Critique(
            score=score,
            approved=approved or score >= self._threshold,
            critique=str(data.get("critique", "")).strip(),
        )
