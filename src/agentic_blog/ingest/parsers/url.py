"""URL parser: fetch a web page over HTTP and reduce it to readable text.

Deliberately minimal — a single direct GET with browser-like headers and a
best-effort main-content extraction. Richer retrieval (search, crawling,
research-ops) is intentionally out of scope for now.
"""

from __future__ import annotations

from urllib.parse import urlparse

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers._textio import html_to_text
from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for

SCHEMES = {"http", "https"}
_TIMEOUT_SECONDS = 15
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _clean_html(raw_html: str) -> tuple[str, str]:
    """Reduce a page to its main content. Returns ``(text, format)``.

    Prefers bs4 to drop boilerplate and select the main content, then
    ``markdownify`` to preserve headings/lists/links as Markdown. Falls back to
    plain text when bs4 or markdownify is unavailable.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html_to_text(raw_html), "text"
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "header", "form", "iframe"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    try:
        from markdownify import markdownify
    except ImportError:
        return str(main.get_text(separator="\n", strip=True)), "text"
    return markdownify(str(main), heading_style="ATX").strip(), "markdown"


def _page_title(raw_html: str, fallback: str) -> str:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw_html, "html.parser")
        if soup.title and soup.title.string:
            return str(soup.title.string).strip()
    except ImportError:
        pass
    return fallback


class UrlParser:
    def can_parse(self, origin: str) -> bool:
        return urlparse(origin).scheme in SCHEMES

    def parse(self, origin: str) -> RawDocument:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency always present
            raise ExtractionError("httpx is required to fetch URLs (`pip install httpx`).") from exc
        try:
            response = httpx.get(
                origin,
                headers=_HEADERS,
                timeout=_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExtractionError(f"Failed to fetch {origin}: {exc}") from exc
        raw_html = response.text
        text, fmt = _clean_html(raw_html)
        if not text.strip():
            raise ExtractionError(f"Fetched {origin} but found no readable text.")
        return RawDocument(
            source_id=source_id_for(origin),
            origin=origin,
            mime="text/html",
            text=text,
            title=_page_title(raw_html, urlparse(origin).netloc or origin),
            metadata={"parser": "url", "format": fmt, "final_url": str(response.url)},
        )
