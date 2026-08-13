"""PDF parser: pymupdf4llm (Markdown) → pdftotext → pypdf → pdfminer (plain-text).

The first extractor produces structured Markdown; the rest are plain-text
fallbacks that fire only when pymupdf4llm is unavailable or yields nothing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for

EXTENSIONS = {".pdf"}


def _with_pymupdf4llm(path: str) -> str | None:
    try:
        import pymupdf4llm
    except ImportError:
        return None
    try:
        return str(pymupdf4llm.to_markdown(path, write_images=False, show_progress=False))
    except Exception:
        return None


def _with_pdftotext(path: str) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", os.path.abspath(path), "-"],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout
    return None


def _with_pypdf(path: str) -> str | None:
    try:
        import pypdf
    except ImportError:
        return None
    try:
        with open(path, "rb") as fh:
            reader = pypdf.PdfReader(fh)
            return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return None


def _with_pdfminer(path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        return None
    try:
        return str(extract_text(path))
    except Exception:
        return None


def _count_pages(path: str) -> int:
    try:
        import pypdf

        with open(path, "rb") as fh:
            return len(pypdf.PdfReader(fh).pages)
    except Exception:
        return 0


class PdfParser:
    def can_parse(self, origin: str) -> bool:
        return Path(origin).suffix.lower() in EXTENSIONS

    def parse(self, origin: str) -> RawDocument:
        for extractor, name, fmt in (
            (_with_pymupdf4llm, "pymupdf4llm", "markdown"),
            (_with_pdftotext, "pdftotext", "text"),
            (_with_pypdf, "pypdf", "text"),
            (_with_pdfminer, "pdfminer", "text"),
        ):
            text = extractor(origin)
            if text and text.strip():
                return RawDocument(
                    source_id=source_id_for(origin),
                    origin=origin,
                    mime="application/pdf",
                    text=text,
                    title=Path(origin).stem,
                    metadata={"parser": name, "format": fmt, "pages": _count_pages(origin)},
                )
        raise ExtractionError(
            f"Could not extract text from PDF: {origin}. "
            "Install `pip install pymupdf4llm` (Markdown) or poppler/`pip install pypdf pdfminer.six`."
        )
