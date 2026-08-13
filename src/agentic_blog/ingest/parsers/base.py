"""Base helpers for parsers: stable source ids and a common failure type."""

from __future__ import annotations

import hashlib
from pathlib import Path

# Bump when the extraction pipeline changes in a way that should invalidate every
# cached ``raw/`` document (better parsing, sanitization, etc.). A cached source
# whose stamped version differs is treated as stale and re-extracted.
EXTRACTOR_VERSION = 1


class ExtractionError(Exception):
    """Raised when a single source cannot be parsed (non-fatal in batch mode)."""


def is_url(origin: str) -> bool:
    """True if the origin is a URL rather than a local path."""
    return "://" in origin


def source_id_for(origin: str) -> str:
    """Derive a stable, short id from a path or URL (the memory dedup key)."""
    normalized = origin.strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    stem = Path(normalized).stem if not is_url(normalized) else normalized.split("/")[-1]
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in stem)[:40].strip("-")
    return f"{stem}-{digest}" if stem else digest


def source_fingerprint(origin: str) -> str | None:
    """Content hash of a local source file (staleness signal), ``None`` for URLs.

    Returns ``None`` for URLs (never-stale policy) and for local paths that no
    longer exist — in both cases there is nothing cheap to compare against, so
    the cached extraction is kept.
    """
    if is_url(origin):
        return None
    path = Path(origin)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
