"""Shared low-level helpers for text-based parsers (BOM-aware decoding, HTML→text)."""

from __future__ import annotations

import html.parser
from pathlib import Path

# Byte-order marks, longest first (UTF-32 LE starts with the UTF-16 LE BOM).
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


def read_text_file(path: str) -> str | None:
    """Read a text file, honoring a BOM and falling back through common encodings."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                break
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


class HTMLTextExtractor(html.parser.HTMLParser):
    """Minimal stdlib HTML → plain-text converter (fallback when bs4 is absent)."""

    SKIP_TAGS = {"script", "style", "head"}
    _BLOCK_TAGS = {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def html_to_text(raw_html: str) -> str:
    """Convert HTML to text, preferring BeautifulSoup, falling back to stdlib."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw_html, "html.parser")
        for element in soup(["script", "style", "head"]):
            element.decompose()
        return str(soup.get_text(separator="\n"))
    except ImportError:
        parser = HTMLTextExtractor()
        parser.feed(raw_html)
        return parser.get_text()
