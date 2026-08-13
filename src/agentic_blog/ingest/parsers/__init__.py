"""Concrete :class:`~agentic_blog.contracts.Parser` implementations.

Each parser is a small, self-contained class that decides whether it can handle
an origin (path suffix or URL scheme) and extracts it into a
:class:`~agentic_blog.contracts.RawDocument`. Optional heavy dependencies are
imported lazily inside each parser so the base install stays light.
"""

from __future__ import annotations

from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for
from agentic_blog.ingest.parsers.docx import DocxParser
from agentic_blog.ingest.parsers.github import GithubParser
from agentic_blog.ingest.parsers.html import HtmlParser
from agentic_blog.ingest.parsers.pdf import PdfParser
from agentic_blog.ingest.parsers.rtf import RtfParser
from agentic_blog.ingest.parsers.text import TextParser
from agentic_blog.ingest.parsers.url import UrlParser

__all__ = [
    "DocxParser",
    "ExtractionError",
    "GithubParser",
    "HtmlParser",
    "PdfParser",
    "RtfParser",
    "TextParser",
    "UrlParser",
    "source_id_for",
]
