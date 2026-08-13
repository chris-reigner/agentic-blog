"""Parser registry: resolve an origin to the first parser that accepts it.

The registry is the single dependency-inversion seam for ingestion. The
:class:`~agentic_blog.ingest.service.IngestService` depends only on the
:class:`~agentic_blog.contracts.Parser` protocol; the concrete ordering lives
here and can be extended without touching the service.
"""

from __future__ import annotations

from agentic_blog.contracts import Parser
from agentic_blog.ingest.parsers import (
    DocxParser,
    GithubParser,
    HtmlParser,
    PdfParser,
    RtfParser,
    TextParser,
    UrlParser,
)


def default_parsers() -> list[Parser]:
    """Built-in parsers, ordered most-specific first.

    ``GithubParser`` precedes ``UrlParser`` so a ``github.com`` repo URL is cloned
    rather than scraped as a single HTML page; ``UrlParser`` then claims any other
    ``http(s)`` scheme. The remaining file parsers are mutually exclusive on suffix.
    """
    return [
        GithubParser(),
        UrlParser(),
        PdfParser(),
        DocxParser(),
        RtfParser(),
        HtmlParser(),
        TextParser(),
    ]


class ParserRegistry:
    """Holds an ordered list of parsers and picks the first that can parse."""

    def __init__(self, parsers: list[Parser] | None = None) -> None:
        self._parsers = parsers if parsers is not None else default_parsers()

    def register(self, parser: Parser) -> None:
        """Prepend a parser so custom handlers win over the defaults."""
        self._parsers.insert(0, parser)

    def parser_for(self, origin: str) -> Parser | None:
        for parser in self._parsers:
            if parser.can_parse(origin):
                return parser
        return None
