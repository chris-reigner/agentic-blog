"""Persist extracted sources as immutable Markdown under a topic's ``raw/`` dir.

Each :class:`~agentic_blog.contracts.RawDocument` becomes one
``<root>/<topic-slug>/raw/<source_id>.md`` file with a small YAML front-matter
header followed by the extracted body. This is the ingest silo's durable output —
the ``raw`` layer of the research-ops-style per-topic directory.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import yaml

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers.base import EXTRACTOR_VERSION, source_fingerprint
from agentic_blog.memory.models import slugify

logger = logging.getLogger(__name__)


class RawStore:
    """Writes extracted documents to ``<root>/<topic-slug>/raw/`` as Markdown."""

    def __init__(self, root: Path | str, *, today: str) -> None:
        self._root = Path(root)
        self._today = today

    def raw_dir(self, topic: str) -> Path:
        return self._root / slugify(topic) / "raw"

    def path_for(self, topic: str, source_id: str) -> Path:
        return self.raw_dir(topic) / f"{slugify(source_id)}.md"

    def read(self, topic: str) -> list[RawDocument]:
        """Reload the raw Markdown written by :meth:`write` back into documents.

        The inverse of :meth:`write`: parses each ``raw/<slug>.md`` file's YAML
        front-matter + body into a :class:`RawDocument` so distill can run as a
        standalone step against already-ingested sources.
        """
        raw_dir = self.raw_dir(topic)
        if not raw_dir.is_dir():
            return []
        documents: list[RawDocument] = []
        for path in sorted(raw_dir.glob("*.md")):
            documents.append(self._parse(path.read_text(encoding="utf-8")))
        return documents

    def read_one(self, topic: str, source_id: str) -> tuple[RawDocument, dict[str, object]] | None:
        """Reload a single cached source plus its front-matter, or ``None`` if absent.

        The front-matter carries the staleness provenance (``extractor_version``,
        ``source_sha256``) the ingest cache needs to decide reuse vs re-extract.
        """
        path = self.path_for(topic, source_id)
        if not path.is_file():
            return None
        content = path.read_text(encoding="utf-8")
        return self._parse(content), self._front(content)

    @staticmethod
    def _front(content: str) -> dict[str, object]:
        if not content.startswith("---\n"):
            return {}
        _, header, _ = content.split("---\n", 2)
        return yaml.safe_load(header) or {}

    def _parse(self, content: str) -> RawDocument:
        front = self._front(content)
        body = content.split("---\n", 2)[2] if content.startswith("---\n") else content
        title = str(front.get("title") or "") or None
        return RawDocument(
            source_id=str(front.get("source_id", "")),
            origin=str(front.get("origin", "")),
            mime=str(front.get("mime", "text/plain")),
            text=body.lstrip("\n").rstrip("\n"),
            title=title,
            metadata={
                "parser": str(front.get("parser", "")),
                "format": str(front.get("format", "text")),
            },
        )

    def write(self, topic: str, documents: Sequence[RawDocument]) -> list[Path]:
        raw_dir = self.raw_dir(topic)
        raw_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for doc in documents:
            path = raw_dir / f"{slugify(doc.source_id)}.md"
            path.write_text(self._render(doc), encoding="utf-8")
            logger.info("Wrote raw source %s", path)
            written.append(path)
        return written

    def _render(self, doc: RawDocument) -> str:
        front: dict[str, object] = {
            "source_id": doc.source_id,
            "origin": doc.origin,
            "mime": doc.mime,
            "title": doc.title or "",
            "parser": str(doc.metadata.get("parser", "")),
            "format": str(doc.metadata.get("format", "text")),
            "ingested": self._today,
            "extractor_version": EXTRACTOR_VERSION,
        }
        fingerprint = source_fingerprint(doc.origin)
        if fingerprint is not None:
            front["source_sha256"] = fingerprint
        header = yaml.safe_dump(front, sort_keys=False, allow_unicode=True).strip()
        return f"---\n{header}\n---\n\n{doc.text}\n"
