"""Distill service: run the distill → critique → revise loop once, on shared Knowledge.

Per the locked design decision (§14), critique happens **once here**, on the
shared ``Knowledge`` — never per rendered artifact. The loop runs until the
critic approves or ``max_iterations`` is reached.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from agentic_blog.contracts import Knowledge, MemoryContext, RawDocument
from agentic_blog.distill.critic import Critic, Critique
from agentic_blog.distill.debate import DebatePanel
from agentic_blog.distill.distiller import Distiller
from agentic_blog.distill.writer import Writer
from agentic_blog.llm import LLMClient
from agentic_blog.settings import DebateSettings, PipelineSettings

logger = logging.getLogger(__name__)


class Reviewer(Protocol):
    """Common surface of :class:`Critic` and :class:`DebatePanel`."""

    def review(self, topic: str, knowledge: Knowledge) -> Critique: ...


@dataclass(slots=True)
class DistillResult:
    """Outcome of distillation: the knowledge plus how it was reached."""

    knowledge: Knowledge
    score: float
    iterations: int
    approved: bool
    critique: str


class DistillService:
    """Orchestrates the single critique loop that produces shared ``Knowledge``."""

    def __init__(
        self,
        llm: LLMClient,
        *,
        pipeline: PipelineSettings,
        debate: DebateSettings,
    ) -> None:
        self._distiller = Distiller(llm)
        self._writer = Writer(llm)
        self._max_iterations = pipeline.max_critique_iterations
        threshold = float(pipeline.approval_threshold)
        self._reviewer: Reviewer = (
            DebatePanel(llm, approval_threshold=threshold, num_personas=debate.num_personas)
            if debate.enabled
            else Critic(llm, approval_threshold=threshold)
        )

    def run(
        self,
        topic: str,
        documents: Sequence[RawDocument],
        context: MemoryContext | None = None,
    ) -> DistillResult:
        logger.info("Distilling %d document(s) for topic %r", len(documents), topic)
        knowledge = self._distiller.distill(topic, documents, context)
        verdict = self._reviewer.review(topic, knowledge)
        iterations = 1

        while not verdict.approved and iterations < self._max_iterations:
            logger.info("Distill iteration %d scored %.1f; revising.", iterations, verdict.score)
            knowledge = self._writer.revise(topic, knowledge, verdict.critique)
            verdict = self._reviewer.review(topic, knowledge)
            iterations += 1

        logger.info(
            "Distill complete: %r scored %.1f in %d iteration(s), approved=%s",
            knowledge.title,
            verdict.score,
            iterations,
            verdict.approved,
        )
        return DistillResult(
            knowledge=knowledge,
            score=verdict.score,
            iterations=iterations,
            approved=verdict.approved,
            critique=verdict.critique,
        )
