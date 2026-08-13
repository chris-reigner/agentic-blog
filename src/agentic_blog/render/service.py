"""Render service: turn one ``Knowledge`` into the requested ``Artifact``s."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from agentic_blog.contracts import Artifact, Knowledge
from agentic_blog.render.registry import RenderRegistry
from agentic_blog.settings import RenderSettings

logger = logging.getLogger(__name__)


class RenderService:
    """Fan one shared ``Knowledge`` out to every requested renderer."""

    def __init__(self, settings: RenderSettings) -> None:
        self._registry = RenderRegistry(settings)

    def render(self, knowledge: Knowledge, kinds: Sequence[str]) -> list[Artifact]:
        logger.info("Rendering %d kind(s): %s", len(kinds), ", ".join(kinds))
        artifacts: list[Artifact] = []
        for renderer in self._registry.build(list(kinds)):
            logger.info("Rendering %s", renderer.kind)
            artifacts.append(renderer.render(knowledge))
        return artifacts
