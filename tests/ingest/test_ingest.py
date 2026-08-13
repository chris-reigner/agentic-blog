"""Ingest silo: registry resolution, batch tolerance, sanitization."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from agentic_blog.ingest.parsers.base import source_id_for
from agentic_blog.ingest.raw_store import RawStore
from agentic_blog.ingest.registry import ParserRegistry
from agentic_blog.ingest.sanitize import sanitize_extracted_text
from agentic_blog.ingest.service import IngestService


def test_registry_resolves_by_extension_and_scheme() -> None:
    registry = ParserRegistry()
    assert type(registry.parser_for("a.pdf")).__name__ == "PdfParser"
    assert type(registry.parser_for("a.md")).__name__ == "TextParser"
    assert type(registry.parser_for("https://x.com")).__name__ == "UrlParser"
    assert registry.parser_for("mystery.zzz") is None


def test_registry_routes_github_repos_to_github_parser() -> None:
    registry = ParserRegistry()
    assert type(registry.parser_for("https://github.com/owner/repo")).__name__ == "GithubParser"
    assert (
        type(registry.parser_for("https://github.com/owner/repo?tab=readme-ov-file")).__name__
        == "GithubParser"
    )
    # A non-repo github.com URL (no owner/repo) falls through to the URL parser.
    assert type(registry.parser_for("https://github.com/features")).__name__ == "UrlParser"


def test_ingest_is_batch_tolerant(tmp_path: Path) -> None:
    good = tmp_path / "note.md"
    good.write_text("# Title\nBody text.", encoding="utf-8")
    result = IngestService().load([str(good), "missing.zzz"])
    assert len(result.documents) == 1
    assert len(result.failures) == 1
    assert result.documents[0].mime == "text/markdown"
    assert result.ok


def test_markdown_files_are_labelled_markdown(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\n- point", encoding="utf-8")
    doc = IngestService().load([str(source)]).documents[0]
    assert doc.mime == "text/markdown"
    assert doc.metadata["format"] == "markdown"


def test_raw_store_writes_markdown_with_front_matter(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Heading\n\nBody.", encoding="utf-8")
    documents = IngestService().load([str(source)]).documents

    store = RawStore(tmp_path / "out", today=date(2026, 8, 13).isoformat())
    written = store.write("My Topic", documents)

    assert len(written) == 1
    page = written[0]
    assert page.parent == tmp_path / "out" / "my-topic" / "raw"
    content = page.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert f"source_id: {documents[0].source_id}" in content
    assert "format: markdown" in content
    assert "# Heading" in content


def test_ingest_sanitizes_invisible_unicode(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("hello​world\U000e0041", encoding="utf-8")
    result = IngestService().load([str(source)])
    assert result.documents[0].text == "helloworld"


def test_sanitize_counts_removed() -> None:
    clean, removed = sanitize_extracted_text("a​﻿b")
    assert clean == "ab"
    assert removed == 2


def test_source_id_is_stable_and_slugged() -> None:
    first = source_id_for("/tmp/Observability Engineering.pdf")
    second = source_id_for("/tmp/Observability Engineering.pdf")
    assert first == second
    assert "observability" in first.lower()
