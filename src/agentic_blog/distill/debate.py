"""Optional multi-persona debate panel (a drop-in replacement for the critic).

When ``debate.enabled`` is true, several personas each score the knowledge from a
distinct stance; their verdicts are aggregated into a single :class:`Critique`.
When disabled, the pipeline uses the single :class:`Critic` instead.
"""

from __future__ import annotations

import logging

from agentic_blog.contracts import Knowledge
from agentic_blog.distill.critic import Critique
from agentic_blog.distill.models import knowledge_to_json
from agentic_blog.distill.prompts import (
    CRITIC_USER,
    DEBATE_PERSONAS,
    DEBATE_SYSTEM,
)
from agentic_blog.llm import LLMClient, extract_json

logger = logging.getLogger(__name__)


class DebatePanel:
    """Aggregates several persona critics into one verdict."""

    def __init__(
        self,
        llm: LLMClient,
        *,
        approval_threshold: float,
        num_personas: int = 3,
    ) -> None:
        self._llm = llm
        self._threshold = approval_threshold
        self._personas = list(DEBATE_PERSONAS)[: max(1, num_personas)]

    def review(self, topic: str, knowledge: Knowledge) -> Critique:
        knowledge_json = knowledge_to_json(knowledge)
        user = CRITIC_USER.format(topic=topic, knowledge_json=knowledge_json)
        scores: list[float] = []
        critiques: list[str] = []
        for persona, stance in self._personas:
            system = DEBATE_SYSTEM.format(persona=persona, stance=stance)
            try:
                data = extract_json(self._llm.complete(system, user))
            except ValueError:
                logger.warning("Persona %s returned unparseable JSON; skipping.", persona)
                continue
            if not isinstance(data, dict):
                continue
            scores.append(float(data.get("score", 0.0)))
            note = str(data.get("critique", "")).strip()
            if note:
                critiques.append(f"[{persona}] {note}")

        if not scores:
            return Critique(score=0.0, approved=False, critique="Panel produced no verdicts.")

        mean_score = sum(scores) / len(scores)
        return Critique(
            score=round(mean_score, 2),
            approved=mean_score >= self._threshold,
            critique="\n".join(critiques),
        )
