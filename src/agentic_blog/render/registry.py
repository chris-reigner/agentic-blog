"""Renderer registry: map ``--render markdown,skill`` to Renderer instances.

Open/Closed seam — adding an output format is registering a new renderer here,
never editing the pipeline. Each renderer is constructed with its
``RenderPolicy`` from config so length/compression are data, not code.
"""

from __future__ import annotations

from collections.abc import Callable

from agentic_blog.contracts import Renderer
from agentic_blog.render.blog import BlogRenderer
from agentic_blog.render.linkedin import LinkedInRenderer
from agentic_blog.render.markdown import MarkdownRenderer
from agentic_blog.render.skill import SkillRenderer
from agentic_blog.settings import RenderPolicy, RenderSettings

# kind -> factory taking its RenderPolicy
_BUILDERS: dict[str, Callable[[RenderPolicy], Renderer]] = {
    "markdown": MarkdownRenderer,
    "blog": BlogRenderer,
    "linkedin": LinkedInRenderer,
    "skill": SkillRenderer,
}

DEFAULT_KINDS = ("markdown",)


def available_kinds() -> tuple[str, ...]:
    return tuple(_BUILDERS)


class RenderRegistry:
    """Builds the requested renderers, each with its configured policy."""

    def __init__(self, settings: RenderSettings) -> None:
        self._settings = settings

    def build(self, kinds: list[str] | tuple[str, ...]) -> list[Renderer]:
        renderers: list[Renderer] = []
        for kind in kinds:
            builder = _BUILDERS.get(kind)
            if builder is None:
                raise ValueError(
                    f"Unknown renderer {kind!r}. Available: {', '.join(available_kinds())}"
                )
            renderers.append(builder(self._settings.policy_for(kind)))
        return renderers
