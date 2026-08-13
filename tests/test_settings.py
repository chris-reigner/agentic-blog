"""Settings load from YAML and validate; secrets come from the environment."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_blog.settings import Settings, load_settings


def test_load_settings_from_project_config() -> None:
    settings = load_settings("config")
    assert settings.pipeline.approval_threshold >= 1
    assert settings.render.kinds  # required, non-empty
    assert settings.render.policy_for("skill").compression == "structural"
    assert settings.render.policy_for("blog").target_words


def test_render_kinds_is_required(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_settings(tmp_path)  # empty dir → render.kinds missing


def test_unknown_render_kind_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("render:\n  kinds: [nope]\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Unknown render kind"):
        load_settings(tmp_path)


def test_other_sections_default_when_omitted(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("render:\n  kinds: [markdown]\n", encoding="utf-8")
    settings = load_settings(tmp_path)
    assert isinstance(settings, Settings)
    assert settings.memory.backend == "markdown"  # defaulted


def test_api_key_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "secret-123")
    from agentic_blog.settings import LLMSettings

    assert LLMSettings().api_key == "secret-123"
