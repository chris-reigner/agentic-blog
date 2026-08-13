"""Typed settings loaded from a single ``config/config.yaml`` with env overrides.

No module in the package hard-codes a tunable; they all read it from here. YAML
holds tunables under one top-level key per silo (``pipeline``, ``llm``,
``render``, ``memory``, ``debate``); the environment holds secrets
(``LLM_API_KEY``). Every model forbids unknown keys, so a typo in the YAML fails
fast at load time with a clear validation error rather than being silently
ignored.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_DIR = Path(os.environ.get("AGENTIC_BLOG_CONFIG", "config"))
CONFIG_FILENAME = "config.yaml"


class _Strict(BaseModel):
    """Base for every settings model: reject unknown keys instead of ignoring them."""

    model_config = ConfigDict(extra="forbid")


class PipelineSettings(_Strict):
    max_critique_iterations: int = 3
    approval_threshold: int = 7
    novelty_window_days: int = 14
    output_root: Path = Path("./output")


class LLMSettings(_Strict):
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "google/gemini-2.0-flash"
    temperature: float = 0.3
    timeout_seconds: float = 90.0
    debate_model: str | None = None
    openrouter_site_url: str = "https://github.com/chris-reigner/agentic-blog"
    openrouter_app_name: str = "agentic-blog"
    # Secret — from the environment only, never from YAML.
    api_key: str = Field(default_factory=lambda: os.environ.get("LLM_API_KEY", ""))

    @property
    def effective_debate_model(self) -> str:
        return self.debate_model or self.model


class RenderPolicy(_Strict):
    compression: Literal["low", "medium", "high", "structural"] = "medium"
    target_words: int | None = None
    hashtags: int | None = None
    seo: bool = False
    skill_md_max_tokens: int | None = None
    chapter_budget_tokens: int | None = None


class RenderSettings(_Strict):
    # Which renderers `run`/`render` produce when no --render flag is given.
    # Required: the pipeline no longer hard-codes a default set.
    kinds: list[str] = Field(..., min_length=1)
    markdown: RenderPolicy = RenderPolicy(compression="low")
    blog: RenderPolicy = RenderPolicy(compression="medium", target_words=1100, seo=True)
    linkedin: RenderPolicy = RenderPolicy(compression="high", hashtags=3)
    skill: RenderPolicy = RenderPolicy(
        compression="structural", skill_md_max_tokens=4000, chapter_budget_tokens=1200
    )

    @field_validator("kinds")
    @classmethod
    def _known_kinds(cls, value: list[str]) -> list[str]:
        known = {name for name in cls.model_fields if name != "kinds"}
        unknown = [k for k in value if k not in known]
        if unknown:
            raise ValueError(
                f"Unknown render kind(s): {', '.join(unknown)}. "
                f"Choose from: {', '.join(sorted(known))}."
            )
        return value

    def policy_for(self, kind: str) -> RenderPolicy:
        return getattr(self, kind, RenderPolicy())


class MemorySettings(_Strict):
    backend: Literal["markdown", "knowledge_base"] = "markdown"
    novelty_window_days: int = 14
    max_lessons_injected: int = 5


class DebateSettings(_Strict):
    enabled: bool = False
    num_personas: int = 3
    rounds: int = 2


class Settings(_Strict):
    """Aggregate settings for the whole application."""

    pipeline: PipelineSettings = PipelineSettings()
    llm: LLMSettings = LLMSettings()
    render: RenderSettings  # required — must declare `render.kinds` in config
    memory: MemorySettings = MemorySettings()
    debate: DebateSettings = DebateSettings()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def load_settings(config: Path | str = DEFAULT_CONFIG_DIR) -> Settings:
    """Load and validate settings from a single ``config.yaml``.

    ``config`` may be the file itself or a directory containing ``config.yaml``
    (the default). ``render.kinds`` is required, so a missing/empty config file
    raises a validation error; unknown keys or bad values do too.
    """
    path = Path(config)
    if path.is_dir():
        path = path / CONFIG_FILENAME
    return Settings(**_load_yaml(path))
