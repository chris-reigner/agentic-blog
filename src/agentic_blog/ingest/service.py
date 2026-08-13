"""Ingest service: turn a batch of origins into clean ``RawDocument`` objects.

Batch-tolerant by design — one unreadable or unsupported source is recorded as
a failure and skipped, never aborting the run. All extracted text is passed
through :func:`sanitize_extracted_text` to strip invisible/adversarial Unicode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers.base import ExtractionError
from agentic_blog.ingest.registry import ParserRegistry
from agentic_blog.ingest.sanitize import sanitize_extracted_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestFailure:
    """A single origin that could not be ingested."""

    origin: str
    reason: str


@dataclass(slots=True)
class IngestResult:
    """Outcome of an ingest batch: successes and per-origin failures."""

    documents: list[RawDocument] = field(default_factory=list)
    failures: list[IngestFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.documents)


class IngestService:
    """Resolve each origin through the registry and extract it to text."""

    def __init__(self, registry: ParserRegistry | None = None) -> None:
        self._registry = registry or ParserRegistry()

    def load(self, sources: list[str]) -> IngestResult:
        logger.info("Ingesting %d source(s)", len(sources))
        result = IngestResult()
        for origin in sources:
            try:
                document = self._load_one(origin)
            except ExtractionError as exc:
                logger.warning("Skipping %s: %s", origin, exc)
                result.failures.append(IngestFailure(origin=origin, reason=str(exc)))
                continue
            except Exception as exc:  # defensive: never let one source abort the batch
                logger.warning("Unexpected error on %s: %s", origin, exc)
                result.failures.append(IngestFailure(origin=origin, reason=repr(exc)))
                continue
            result.documents.append(document)
        logger.info(
            "Ingest complete: %d ok, %d failed", len(result.documents), len(result.failures)
        )
        return result

    def _load_one(self, origin: str) -> RawDocument:
        parser = self._registry.parser_for(origin)
        if parser is None:
            raise ExtractionError(f"No parser knows how to handle: {origin}")
        document = parser.parse(origin)
        cleaned, removed = sanitize_extracted_text(document.text)
        if removed:
            logger.debug("Sanitized %d invisible codepoints from %s", removed, origin)
            document = replace(document, text=cleaned)
        return document
