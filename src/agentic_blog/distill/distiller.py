"""Distiller: RawDocument(s) + memory context → a first ``Knowledge`` draft."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from agentic_blog.contracts import Knowledge, MemoryContext, RawDocument
from agentic_blog.distill.models import knowledge_from_dict
from agentic_blog.distill.prompts import DISTILL_SYSTEM, DISTILL_USER
from agentic_blog.llm import LLMClient, extract_json

logger = logging.getLogger(__name__)

# Rough char budget for the source material sent to the model (~ a large context
# window). Deliberately simple; smarter chunking is a later concern.
_MATERIAL_CHAR_BUDGET = 120_000


def _assemble_material(documents: Sequence[RawDocument]) -> str:
    parts: list[str] = []
    per_doc = max(2_000, _MATERIAL_CHAR_BUDGET // max(len(documents), 1))
    for doc in documents:
        header = f"# {doc.title or doc.origin} ({doc.origin})"
        parts.append(f"{header}\n{doc.text[:per_doc]}")
    return "\n\n".join(parts)


class Distiller:
    """One deep pass that extracts structure into a ``Knowledge`` object."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def distill(
        self,
        topic: str,
        documents: Sequence[RawDocument],
        context: MemoryContext | None = None,
    ) -> Knowledge:
        material = _assemble_material(documents)
        memory_block = context.as_prompt_block() if context else ""
        user = DISTILL_USER.format(
            topic=topic,
            memory_block=memory_block or "(no prior memory for this topic)",
            material=material,
        )
        raw = self._llm.complete(DISTILL_SYSTEM, user)
        data = extract_json(raw)
        if not isinstance(data, dict):
            raise ValueError("Distiller expected a JSON object.")
        return knowledge_from_dict(
            data,
            provenance=[doc.origin for doc in documents],
            metadata={"topic": topic, "source_ids": [d.source_id for d in documents]},
        )
