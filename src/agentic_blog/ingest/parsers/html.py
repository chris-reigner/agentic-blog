"""HTML file parser (bs4 preferred, stdlib fallback)."""

from __future__ import annotations

from pathlib import Path

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers._textio import html_to_text, read_text_file
from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for

EXTENSIONS = {".html", ".htm", ".xhtml"}


class HtmlParser:
    def can_parse(self, origin: str) -> bool:
        return Path(origin).suffix.lower() in EXTENSIONS

    def parse(self, origin: str) -> RawDocument:
        raw = read_text_file(origin)
        if raw is None:
            raise ExtractionError(f"Could not read HTML file: {origin}")
        return RawDocument(
            source_id=source_id_for(origin),
            origin=origin,
            mime="text/html",
            text=html_to_text(raw),
            title=Path(origin).stem,
            metadata={"parser": "html"},
        )
