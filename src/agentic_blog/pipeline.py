"""``Pipeline`` — the public library façade over the four silos + graph.

    from agentic_blog import Pipeline
    pipe = Pipeline.from_config("config/")
    result = pipe.run(topic="observability", sources=["book.pdf"], renders=["blog", "skill"])

A run resolves to a per-topic directory ``output/<topic-slug>/`` holding both the
memory layer and the rendered ``artifacts/`` — a durable, self-contained topic KB.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from agentic_blog.contracts import Artifact, Knowledge, RawDocument
from agentic_blog.distill.models import knowledge_from_dict
from agentic_blog.distill.service import DistillService
from agentic_blog.graph import Silos, build_graph
from agentic_blog.ingest import cache
from agentic_blog.ingest.raw_store import RawStore
from agentic_blog.ingest.service import IngestFailure, IngestService
from agentic_blog.llm import LLMClient, OpenAICompatibleClient
from agentic_blog.memory.models import slugify
from agentic_blog.memory.wiki import Memory, build_store
from agentic_blog.render.service import RenderService
from agentic_blog.settings import DebateSettings, Settings, load_settings
from agentic_blog.state import PipelineState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunResult:
    """Outcome of a pipeline run."""

    topic: str
    topic_dir: Path
    artifacts: dict[str, Artifact]
    knowledge: Knowledge
    score: float
    iterations: int
    approved: bool
    ingest_failures: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IngestRunResult:
    """Outcome of an ingest-only run (ingest → extract → persist raw)."""

    topic: str
    topic_dir: Path
    raw_dir: Path
    documents: list[RawDocument]
    raw_paths: list[Path]
    failures: list[IngestFailure]
    reused: list[str] = field(default_factory=list)
    extracted: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DistillRunResult:
    """Outcome of a distill-only run (reload raw → distill → persist knowledge)."""

    topic: str
    topic_dir: Path
    knowledge: Knowledge
    score: float
    iterations: int
    approved: bool
    critique: str
    documents: int
    output_paths: list[Path]


@dataclass(slots=True)
class RenderRunResult:
    """Outcome of a render-only run (reload distilled knowledge → render artifacts)."""

    topic: str
    topic_dir: Path
    artifacts: dict[str, Artifact]
    statuses: list[tuple[Path, str]]  # (dest, "created" | "updated" | "unchanged")
    sources: list[str]
    log_path: Path


class Pipeline:
    """Wires the silos and runs the graph. Construct via :meth:`from_config`."""

    def __init__(
        self,
        settings: Settings,
        *,
        llm: LLMClient | None = None,
        today: str | None = None,
    ) -> None:
        self._settings = settings
        self._today = today or date.today().isoformat()
        self._llm = llm or OpenAICompatibleClient(settings.llm)

    @classmethod
    def from_config(
        cls,
        config_dir: Path | str = "config",
        *,
        llm: LLMClient | None = None,
        today: str | None = None,
    ) -> Pipeline:
        return cls(load_settings(config_dir), llm=llm, today=today)

    def _build_silos(self, debate: DebateSettings) -> Silos:
        output_root = self._settings.pipeline.output_root
        store = build_store(self._settings.memory, output_root, today=self._today)
        return Silos(
            ingest=IngestService(),
            memory=Memory(store),
            distill=DistillService(self._llm, pipeline=self._settings.pipeline, debate=debate),
            render=RenderService(self._settings.render),
            raw_store=RawStore(output_root, today=self._today),
        )

    def ingest(
        self, topic: str, sources: Sequence[str], *, reextract: bool = False
    ) -> IngestRunResult:
        """Ingest → extract → persist raw Markdown, stopping before distill.

        Exercises the real ingest path (registry resolution + sanitization via
        :class:`IngestService`) and writes each extracted source to
        ``output/<topic-slug>/raw/<source_id>.md``. No LLM is required.

        By default already-extracted, unchanged sources are reused from
        ``raw/`` instead of being re-parsed; pass ``reextract=True`` to force a
        fresh extraction of every source.
        """
        output_root = self._settings.pipeline.output_root
        raw_store = RawStore(output_root, today=self._today)
        resolved = cache.resolve(
            IngestService(), raw_store, topic, list(sources), reextract=reextract
        )
        raw_paths = [raw_store.path_for(topic, doc.source_id) for doc in resolved.documents]
        return IngestRunResult(
            topic=topic,
            topic_dir=Path(output_root) / slugify(topic),
            raw_dir=raw_store.raw_dir(topic),
            documents=resolved.documents,
            raw_paths=raw_paths,
            failures=resolved.failures,
            reused=resolved.reused,
            extracted=resolved.extracted,
        )

    def distill(self, topic: str, *, debate: bool | None = None) -> DistillRunResult:
        """Reload ``raw/`` for a topic and run the distill → critique → revise loop.

        Runs distill as a standalone step (no ingest, no render) against whatever
        LLM backend is configured. Persists the distilled ``Knowledge`` as both a
        structured ``distilled/knowledge.json`` and a readable ``distilled/knowledge.md``.
        """
        output_root = self._settings.pipeline.output_root
        raw_store = RawStore(output_root, today=self._today)
        documents = raw_store.read(topic)
        if not documents:
            raise FileNotFoundError(
                f"No raw sources under {raw_store.raw_dir(topic)}. Run `ingest` first."
            )
        logger.info("Distill start: topic=%r sources=%d", topic, len(documents))

        debate_settings = self._settings.debate
        if debate is not None:
            debate_settings = debate_settings.model_copy(update={"enabled": debate})

        service = DistillService(
            self._llm, pipeline=self._settings.pipeline, debate=debate_settings
        )
        result = service.run(topic, documents, None)

        topic_dir = Path(output_root) / slugify(topic)
        output_paths = self._write_distilled(topic_dir, result.knowledge)
        return DistillRunResult(
            topic=topic,
            topic_dir=topic_dir,
            knowledge=result.knowledge,
            score=result.score,
            iterations=result.iterations,
            approved=result.approved,
            critique=result.critique,
            documents=len(documents),
            output_paths=output_paths,
        )

    def _write_distilled(self, topic_dir: Path, knowledge: Knowledge) -> list[Path]:
        dest_dir = topic_dir / "distilled"
        dest_dir.mkdir(parents=True, exist_ok=True)
        json_path = dest_dir / "knowledge.json"
        json_path.write_text(
            json.dumps(asdict(knowledge), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        md_path = dest_dir / "knowledge.md"
        artifact = RenderService(self._settings.render).render(knowledge, ["markdown"])[0]
        md_path.write_text(next(iter(artifact.files.values())), encoding="utf-8")
        logger.info("Wrote distilled knowledge to %s and %s", json_path, md_path)
        return [json_path, md_path]

    def render(self, topic: str, *, renders: Sequence[str] | None = None) -> RenderRunResult:
        """Reload a topic's distilled ``knowledge.json`` and render artifacts.

        Runs render as a standalone step (no ingest, no distill, no LLM). Rebuilds
        the shared ``Knowledge`` from ``distilled/knowledge.json``, stamps the
        current date as ``created`` provenance, fans it out to every requested
        renderer, writes each artifact under ``artifacts/<kind>/`` (reporting
        created/updated/unchanged per file), and appends a render log entry.
        """
        renders = list(renders or self._settings.render.kinds)
        output_root = self._settings.pipeline.output_root
        topic_dir = Path(output_root) / slugify(topic)
        knowledge_path = topic_dir / "distilled" / "knowledge.json"
        if not knowledge_path.exists():
            raise FileNotFoundError(
                f"No distilled knowledge at {knowledge_path}. Run `distill` first."
            )

        data = json.loads(knowledge_path.read_text(encoding="utf-8"))
        metadata = {**data.get("metadata", {}), "created": self._today}
        knowledge = knowledge_from_dict(
            data, provenance=data.get("provenance", ()), metadata=metadata
        )
        logger.info("Render start: topic=%r renders=%s", topic, renders)

        artifacts_list = RenderService(self._settings.render).render(knowledge, renders)
        artifacts = {a.kind: a for a in artifacts_list}
        statuses = self._write_artifacts(topic_dir, artifacts_list)
        sources = list(knowledge.provenance)
        log_path = self._append_render_log(topic_dir, topic, renders, statuses, sources)
        logger.info("Render complete: %d artifact(s) -> %s", len(statuses), topic_dir)
        return RenderRunResult(
            topic=topic,
            topic_dir=topic_dir,
            artifacts=artifacts,
            statuses=statuses,
            sources=sources,
            log_path=log_path,
        )

    def run(
        self,
        topic: str,
        sources: Sequence[str],
        *,
        renders: Sequence[str] | None = None,
        debate: bool | None = None,
        reextract: bool = False,
        thread_id: str | None = None,
    ) -> RunResult:
        renders = list(renders or self._settings.render.kinds)
        debate_settings = self._settings.debate
        if debate is not None:
            debate_settings = debate_settings.model_copy(update={"enabled": debate})

        logger.info(
            "Run start: topic=%r sources=%d renders=%s debate=%s",
            topic,
            len(sources),
            renders,
            debate_settings.enabled,
        )
        silos = self._build_silos(debate_settings)
        output_root = self._settings.pipeline.output_root
        topic_dir = Path(output_root) / slugify(topic)
        checkpoint_path = topic_dir / ".checkpoints.sqlite"

        graph = build_graph(silos, checkpoint_path=checkpoint_path)
        initial: PipelineState = {
            "topic": topic,
            "sources": list(sources),
            "renders": renders,
            "run_date": self._today,
            "reextract": reextract,
        }
        config = {"configurable": {"thread_id": thread_id or slugify(topic)}}
        final: PipelineState = graph.invoke(initial, config)

        artifacts = {a.kind: a for a in final.get("artifacts", [])}
        self._write_artifacts(topic_dir, final.get("artifacts", []))

        logger.info(
            "Run complete: score=%.1f approved=%s -> %s",
            final.get("score", 0.0),
            final.get("approved", False),
            topic_dir,
        )
        return RunResult(
            topic=topic,
            topic_dir=topic_dir,
            artifacts=artifacts,
            knowledge=final["knowledge"],
            score=final.get("score", 0.0),
            iterations=final.get("iterations", 0),
            approved=final.get("approved", False),
            ingest_failures=final.get("ingest_failures", []),
        )

    def _write_artifacts(
        self, topic_dir: Path, artifacts: Sequence[Artifact]
    ) -> list[tuple[Path, str]]:
        """Persist artifacts under ``artifacts/<kind>/``; report per-file status.

        Always overwrites, but classifies each file as ``created`` (new),
        ``updated`` (content differed), or ``unchanged`` (byte-identical) so a
        re-render is transparent about what actually moved.
        """
        statuses: list[tuple[Path, str]] = []
        for artifact in artifacts:
            base = topic_dir / "artifacts" / artifact.kind
            for rel_path, content in artifact.files.items():
                dest = base / rel_path
                if not dest.exists():
                    status = "created"
                elif dest.read_text(encoding="utf-8") == content:
                    status = "unchanged"
                else:
                    status = "updated"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
                logger.info("Wrote %s (%s)", dest, status)
                statuses.append((dest, status))
        return statuses

    def _append_render_log(
        self,
        topic_dir: Path,
        topic: str,
        renders: Sequence[str],
        statuses: Sequence[tuple[Path, str]],
        sources: Sequence[str],
    ) -> Path:
        """Append an idempotent, dated entry to ``artifacts/log.md``."""
        log_path = topic_dir / "artifacts" / "log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"## [{self._today}] render | {topic} | {', '.join(renders)}",
            f"- renders: {', '.join(renders)}",
            f"- sources: {len(sources)}" + (f" — {', '.join(sources)}" if sources else ""),
            "- artifacts:",
        ]
        for dest, status in statuses:
            rel = dest.relative_to(topic_dir)
            lines.append(f"  - {rel} ({status})")
        entry = "\n".join(lines) + "\n\n"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        return log_path
