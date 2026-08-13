"""Plain-text / Markdown / reStructuredText / AsciiDoc parser."""

from __future__ import annotations

from pathlib import Path

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers._textio import read_text_file
from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for

EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc"}
_MARKDOWN_EXTENSIONS = {".md", ".markdown"}


class TextParser:
    """Reads text-native formats with BOM-aware decoding."""

    def can_parse(self, origin: str) -> bool:
        return Path(origin).suffix.lower() in EXTENSIONS

    def parse(self, origin: str) -> RawDocument:
        text = read_text_file(origin)
        if text is None:
            raise ExtractionError(f"Could not read text file: {origin}")
        is_markdown = Path(origin).suffix.lower() in _MARKDOWN_EXTENSIONS
        return RawDocument(
            source_id=source_id_for(origin),
            origin=origin,
            mime="text/markdown" if is_markdown else "text/plain",
            text=text,
            title=Path(origin).stem,
            metadata={"parser": "text", "format": "markdown" if is_markdown else "text"},
        )
