"""Ingest cache: reuse already-extracted ``raw/`` documents instead of re-parsing.

Extraction is the expensive, deterministic front of the pipeline. Because a
source's ``source_id`` (and therefore its ``raw/<id>.md`` path) is a pure
function of the origin, we can decide *before* extracting whether a usable copy
already exists. A cached source is reused unless:

- ``reextract`` is forced (``--reingest``), or
- its stamped ``extractor_version`` is older than the current one (extraction
  improved), or
- it is a local file whose content hash changed.

URLs are never stale (once fetched they are treated as immutable) — refresh them
with ``--reingest`` or by bumping ``EXTRACTOR_VERSION``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers.base import (
    EXTRACTOR_VERSION,
    is_url,
    source_fingerprint,
    source_id_for,
)
from agentic_blog.ingest.raw_store import RawStore
from agentic_blog.ingest.service import IngestFailure, IngestService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CachedIngestResult:
    """Ingest outcome that distinguishes reused from freshly extracted sources."""

    documents: list[RawDocument] = field(default_factory=list)
    failures: list[IngestFailure] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)  # origins served from cache
    extracted: list[str] = field(default_factory=list)  # origins (re)extracted


def _is_stale(origin: str, front: dict[str, object]) -> bool:
    if str(front.get("extractor_version", "")) != str(EXTRACTOR_VERSION):
        return True
    if is_url(origin):
        return False  # never-stale policy for URLs
    fingerprint = source_fingerprint(origin)
    if fingerprint is None:
        return False  # source gone/unreadable — keep the cached copy
    return str(front.get("source_sha256", "")) != fingerprint


def resolve(
    service: IngestService,
    raw_store: RawStore,
    topic: str,
    sources: list[str],
    *,
    reextract: bool = False,
) -> CachedIngestResult:
    """Reuse cached extractions where possible; extract (and persist) the rest.

    Preserves input order and de-duplicates repeated origins. Freshly extracted
    documents are written to ``raw/``; reused ones are already on disk.
    """
    resolved: dict[str, RawDocument] = {}
    reused: list[str] = []
    to_extract: list[str] = []

    for origin in sources:
        if origin in resolved or origin in to_extract:
            continue  # de-dupe repeated origins
        cached = None if reextract else raw_store.read_one(topic, source_id_for(origin))
        if cached is not None and not _is_stale(origin, cached[1]):
            resolved[origin] = cached[0]
            reused.append(origin)
            logger.info("Reusing cached extraction for %s", origin)
        else:
            to_extract.append(origin)

    failures: list[IngestFailure] = []
    extracted: list[str] = []
    if to_extract:
        fresh = service.load(to_extract)
        raw_store.write(topic, fresh.documents)
        for doc in fresh.documents:
            resolved[doc.origin] = doc
            extracted.append(doc.origin)
        failures = fresh.failures

    documents = [resolved[o] for o in sources if o in resolved]
    logger.info(
        "Ingest cache: %d reused, %d extracted, %d failed",
        len(reused),
        len(extracted),
        len(failures),
    )
    return CachedIngestResult(
        documents=documents, failures=failures, reused=reused, extracted=extracted
    )
