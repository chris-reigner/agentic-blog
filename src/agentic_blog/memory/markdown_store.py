"""Markdown-first :class:`MemoryStore` — the default backend.

One directory per topic under ``root``:

    <topic-slug>/
      index.yaml            # canonical catalog (dedup key = source_id)
      index.md              # human-readable regeneration of index.yaml
      entries/<slug>.md     # one page per source ingested
      lessons.md            # weighted editorial lessons from low-scoring runs
      log.md                # append-only run log

``index.yaml`` is authoritative; ``index.md`` is regenerated from it. No database.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from agentic_blog.contracts import MemoryContext, MemoryEntry, RunRecord
from agentic_blog.memory.models import (
    LESSON_PURGE_THRESHOLD,
    Lesson,
    keywords_from_text,
    overlap_ratio,
    slugify,
)

_LESSON_ITERATION_THRESHOLD = 2  # record a lesson when a run needed ≥ this many critics


class MarkdownStore:
    """Filesystem-backed memory. Implements the ``MemoryStore`` Protocol."""

    def __init__(
        self,
        root: Path,
        *,
        novelty_window_days: int = 14,
        max_lessons_injected: int = 5,
        today: str,
    ) -> None:
        self._root = Path(root)
        self._novelty_window_days = novelty_window_days
        self._max_lessons = max_lessons_injected
        # Injected rather than read from the clock: keeps the store deterministic
        # and testable. The caller (Memory façade) supplies the run date.
        self._today = today

    # ── paths ─────────────────────────────────────────────────────────────────

    def _topic_dir(self, topic: str) -> Path:
        return self._root / slugify(topic)

    def _index_path(self, topic: str) -> Path:
        return self._topic_dir(topic) / "index.yaml"

    # ── read path ───────────────────────────────────────────────────────────────

    def _load_index(self, topic: str) -> list[MemoryEntry]:
        path = self._index_path(topic)
        if not path.exists():
            return []
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_entries = data.get("entries", []) if isinstance(data, dict) else []
        entries: list[MemoryEntry] = []
        for item in raw_entries:
            if not isinstance(item, dict) or "source_id" not in item:
                continue
            entries.append(
                MemoryEntry(
                    source_id=str(item["source_id"]),
                    title=str(item.get("title", "")),
                    added=str(item.get("added", "")),
                    score=float(item.get("score", 0.0)),
                    iterations=int(item.get("iterations", 0)),
                    keywords=list(item.get("keywords", [])),
                    origin=str(item.get("origin", "")),
                )
            )
        return entries

    def already_ingested(self, topic: str, source_id: str) -> bool:
        return any(e.source_id == source_id for e in self._load_index(topic))

    def context_for(self, topic: str, source_ids: Sequence[str]) -> MemoryContext:
        entries = self._load_index(topic)
        if not entries:
            return MemoryContext(topic=topic)

        # Related = entries sharing keywords with the incoming sources' ids/slugs.
        incoming_kw = set()
        for sid in source_ids:
            incoming_kw.update(keywords_from_text(sid, "", limit=6))
        related = sorted(
            entries,
            key=lambda e: overlap_ratio(incoming_kw, set(e.keywords)),
            reverse=True,
        )[:3]

        recent_titles = [e.title for e in entries[: self._novelty_window_cap()] if e.title]
        lessons = [
            f"[{lesson.weight:.2f}] {lesson.critique}" for lesson in self._top_lessons(topic)
        ]

        return MemoryContext(
            topic=topic,
            related=tuple(related),
            recent_titles=tuple(recent_titles),
            lessons=tuple(lessons),
        )

    def _novelty_window_cap(self) -> int:
        # Entries are stored newest-first; cap the "recent" list generously.
        return max(5, self._novelty_window_days // 2)

    # ── write path ───────────────────────────────────────────────────────────────

    def record(self, run: RunRecord) -> None:
        topic_dir = self._topic_dir(run.topic)
        (topic_dir / "entries").mkdir(parents=True, exist_ok=True)

        run_date = run.run_date or self._today
        existing = {e.source_id: e for e in self._load_index(run.topic)}

        for source in run.sources:
            entry = MemoryEntry(
                source_id=source.source_id,
                title=source.title or run.title,
                added=source.added or run_date,
                score=run.score,
                iterations=run.iterations,
                keywords=source.keywords or keywords_from_text(source.title or run.title, ""),
                origin=source.origin,
            )
            existing[entry.source_id] = entry
            self._write_entry_page(topic_dir, entry, run)

        ordered = sorted(existing.values(), key=lambda e: e.added, reverse=True)
        self._write_index(run.topic, ordered)
        self._append_log(topic_dir, run, run_date)
        if run.iterations >= _LESSON_ITERATION_THRESHOLD and run.critique:
            self._append_lesson(run.topic, run, run_date)

    def _write_entry_page(self, topic_dir: Path, entry: MemoryEntry, run: RunRecord) -> None:
        page = topic_dir / "entries" / f"{slugify(entry.source_id)}.md"
        page.write_text(
            f"# {entry.title}\n\n"
            f"- Source id: `{entry.source_id}`\n"
            f"- Origin: {entry.origin or '—'}\n"
            f"- Added: {entry.added}\n"
            f"- Last run score: {entry.score} (iterations: {entry.iterations})\n"
            f"- Keywords: {', '.join(entry.keywords) or '—'}\n",
            encoding="utf-8",
        )

    def _write_index(self, topic: str, entries: list[MemoryEntry]) -> None:
        topic_dir = self._topic_dir(topic)
        payload = {
            "topic": topic,
            "entries": [
                {
                    "source_id": e.source_id,
                    "title": e.title,
                    "added": e.added,
                    "score": e.score,
                    "iterations": e.iterations,
                    "keywords": list(e.keywords),
                    "origin": e.origin,
                }
                for e in entries
            ],
        }
        (topic_dir / "index.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        self._write_index_md(topic_dir, topic, entries)

    def _write_index_md(self, topic_dir: Path, topic: str, entries: list[MemoryEntry]) -> None:
        lines = [
            f"# Memory — {topic}",
            "",
            "_Regenerated from `index.yaml` (do not edit by hand)._",
            "",
            "| Added | Title | Score | Keywords |",
            "|-------|-------|-------|----------|",
        ]
        for e in entries:
            kws = ", ".join(e.keywords)
            title = e.title.replace("|", "-")
            lines.append(f"| {e.added} | {title} | {e.score} | {kws} |")
        (topic_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_log(self, topic_dir: Path, run: RunRecord, run_date: str) -> None:
        log = topic_dir / "log.md"
        header = "" if log.exists() else "# Run log\n\n"
        source_ids = ", ".join(s.source_id for s in run.sources) or "—"
        line = (
            f"- **{run_date}** — {run.title} "
            f"(score: {run.score}, iterations: {run.iterations}; sources: {source_ids})\n"
        )
        with log.open("a", encoding="utf-8") as fh:
            fh.write(header + line)

    # ── lessons ──────────────────────────────────────────────────────────────────

    def _lessons_path(self, topic: str) -> Path:
        return self._topic_dir(topic) / "lessons.md"

    def _load_lessons(self, topic: str) -> list[Lesson]:
        path = self._lessons_path(topic)
        if not path.exists():
            return []
        lessons: list[Lesson] = []
        current: dict[str, Any] | None = None

        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(
                r"^## (\d{4}-\d{2}-\d{2}) \| iterations: (\d+) \| "
                r"score: ([\d.]+) \| weight: ([\d.]+)",
                line,
            )
            if m:
                if current:
                    lessons.append(Lesson(**current))
                current = {
                    "added": m.group(1),
                    "iterations": int(m.group(2)),
                    "score": float(m.group(3)),
                    "weight": float(m.group(4)),
                    "critique": "",
                }
            elif current is not None and line.startswith("- "):
                current["critique"] = line[2:].strip()
        if current:
            lessons.append(Lesson(**current))
        return lessons

    def _top_lessons(self, topic: str) -> list[Lesson]:
        lessons = sorted(self._load_lessons(topic), key=lambda x: x.weight, reverse=True)
        return lessons[: self._max_lessons]

    def _append_lesson(self, topic: str, run: RunRecord, run_date: str) -> None:
        # Decay existing lessons, purge the faded ones, then prepend the new one.
        kept = [
            decayed
            for decayed in (existing.decayed() for existing in self._load_lessons(topic))
            if decayed.weight >= LESSON_PURGE_THRESHOLD
        ]
        new = Lesson(
            added=run_date,
            iterations=run.iterations,
            score=run.score,
            weight=1.0,
            critique=run.critique.strip().replace("\n", " ")[:300],
        )
        self._write_lessons(topic, [new, *kept])

    def _write_lessons(self, topic: str, lessons: list[Lesson]) -> None:
        lines = [f"# Editorial lessons — {topic}", ""]
        for lesson in lessons:
            lines.append(
                f"## {lesson.added} | iterations: {lesson.iterations} | "
                f"score: {lesson.score} | weight: {lesson.weight:.2f}"
            )
            lines.append(f"- {lesson.critique}")
            lines.append("")
        self._lessons_path(topic).write_text("\n".join(lines), encoding="utf-8")
