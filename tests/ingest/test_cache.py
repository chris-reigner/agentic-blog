"""Ingest cache: reuse extracted raw/ documents, force re-extraction, staleness."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from agentic_blog.ingest import cache
from agentic_blog.ingest.parsers.base import EXTRACTOR_VERSION
from agentic_blog.ingest.raw_store import RawStore
from agentic_blog.ingest.service import IngestService

TODAY = date(2026, 8, 13).isoformat()


def _store(tmp_path: Path) -> RawStore:
    return RawStore(tmp_path / "out", today=TODAY)


def test_second_ingest_reuses_cached_extraction(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\nBody.", encoding="utf-8")
    store = _store(tmp_path)

    first = cache.resolve(IngestService(), store, "topic", [str(source)])
    assert first.extracted == [str(source)]
    assert first.reused == []

    second = cache.resolve(IngestService(), store, "topic", [str(source)])
    assert second.reused == [str(source)]
    assert second.extracted == []
    assert second.documents[0].text == first.documents[0].text


def test_reextract_forces_fresh_extraction(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\nBody.", encoding="utf-8")
    store = _store(tmp_path)

    cache.resolve(IngestService(), store, "topic", [str(source)])
    forced = cache.resolve(IngestService(), store, "topic", [str(source)], reextract=True)
    assert forced.extracted == [str(source)]
    assert forced.reused == []


def test_changed_local_source_is_re_extracted(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\nOriginal.", encoding="utf-8")
    store = _store(tmp_path)

    cache.resolve(IngestService(), store, "topic", [str(source)])
    source.write_text("# Heading\n\nEdited body.", encoding="utf-8")
    again = cache.resolve(IngestService(), store, "topic", [str(source)])
    assert again.extracted == [str(source)]
    assert "Edited body." in again.documents[0].text


def test_extractor_version_bump_invalidates_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\nBody.", encoding="utf-8")
    store = _store(tmp_path)
    cache.resolve(IngestService(), store, "topic", [str(source)])

    monkeypatch.setattr(cache, "EXTRACTOR_VERSION", EXTRACTOR_VERSION + 1)
    again = cache.resolve(IngestService(), store, "topic", [str(source)])
    assert again.extracted == [str(source)]


def test_order_preserved_with_mixed_reuse(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# A", encoding="utf-8")
    b.write_text("# B", encoding="utf-8")
    store = _store(tmp_path)

    cache.resolve(IngestService(), store, "topic", [str(a)])  # cache only a
    result = cache.resolve(IngestService(), store, "topic", [str(a), str(b)])
    origins = [d.origin for d in result.documents]
    assert origins == [str(a), str(b)]
    assert result.reused == [str(a)]
    assert result.extracted == [str(b)]
