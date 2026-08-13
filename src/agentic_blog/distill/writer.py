"""Writer: revise a ``Knowledge`` to address editorial critique."""

from __future__ import annotations

import logging

from agentic_blog.contracts import Knowledge
from agentic_blog.distill.models import knowledge_from_dict, knowledge_to_json
from agentic_blog.distill.prompts import WRITER_SYSTEM, WRITER_USER
from agentic_blog.llm import LLMClient, extract_json

logger = logging.getLogger(__name__)


class Writer:
    """Refines knowledge in response to a critique, preserving the contract."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def revise(self, topic: str, knowledge: Knowledge, critique: str) -> Knowledge:
        user = WRITER_USER.format(
            topic=topic,
            knowledge_json=knowledge_to_json(knowledge),
            critique=critique or "(no specific critique; improve specificity and structure)",
        )
        raw = self._llm.complete(WRITER_SYSTEM, user)
        try:
            data = extract_json(raw)
        except ValueError:
            logger.warning("Writer returned unparseable JSON; keeping prior knowledge.")
            return knowledge
        if not isinstance(data, dict):
            return knowledge
        revised = knowledge_from_dict(
            data, provenance=knowledge.provenance, metadata=knowledge.metadata
        )
        # Never let a revision collapse the knowledge to nothing.
        if not revised.sections and not revised.frameworks:
            return knowledge
        return revised
