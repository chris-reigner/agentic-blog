"""Ingest silo: sources → normalized, sanitized :class:`RawDocument` objects.

Public surface is the :class:`IngestService`; parsers and the registry are the
extension points. This silo knows nothing about distillation, rendering, or
memory — it only produces text.
"""

from __future__ import annotations

from agentic_blog.ingest.dependencies import format_report, probe
from agentic_blog.ingest.registry import ParserRegistry, default_parsers
from agentic_blog.ingest.sanitize import sanitize_extracted_text
from agentic_blog.ingest.service import (
    IngestFailure,
    IngestResult,
    IngestService,
)

__all__ = [
    "IngestFailure",
    "IngestResult",
    "IngestService",
    "ParserRegistry",
    "default_parsers",
    "format_report",
    "probe",
    "sanitize_extracted_text",
]
