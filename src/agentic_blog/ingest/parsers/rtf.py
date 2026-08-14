"""RTF parser: striprtf preferred, minimal control-word stripping fallback."""

from __future__ import annotations

import re
from pathlib import Path

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers._textio import read_text_file
from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for

EXTENSIONS = {".rtf"}


def _with_striprtf(raw: str) -> str | None:
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError:
        return None
    try:
        return str(rtf_to_text(raw))  # type: ignore[no-untyped-call]
    except Exception:
        return None


def _strip_fallback(raw: str) -> str:
    """Very small RTF stripper: drop control words, groups and escapes."""
    text = re.sub(r"\\'[0-9a-fA-F]{2}", "", raw)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("\\*", "")
    text = re.sub(r"[{}]", "", text)
    return text


class RtfParser:
    def can_parse(self, origin: str) -> bool:
        return Path(origin).suffix.lower() in EXTENSIONS

    def parse(self, origin: str) -> RawDocument:
        raw = read_text_file(origin)
        if raw is None:
            raise ExtractionError(f"Could not read RTF file: {origin}")
        text = _with_striprtf(raw)
        parser_name = "striprtf"
        if not (text and text.strip()):
            text = _strip_fallback(raw)
            parser_name = "fallback"
        if not text.strip():
            raise ExtractionError(f"Could not extract text from RTF: {origin}")
        return RawDocument(
            source_id=source_id_for(origin),
            origin=origin,
            mime="application/rtf",
            text=text,
            title=Path(origin).stem,
            metadata={"parser": parser_name},
        )
