"""Thin Typer CLI over the :class:`Pipeline` library surface.

agentic-blog run ./book.pdf --topic observability --render blog,skill
agentic-blog run --url https://example.com/post --topic obs --render markdown --debate
agentic-blog check
agentic-blog memory list
agentic-blog memory show observability
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import typer
import yaml

from agentic_blog.ingest.dependencies import format_report
from agentic_blog.ingest.registry import ParserRegistry
from agentic_blog.logging import configure_logging
from agentic_blog.memory.models import slugify
from agentic_blog.pipeline import Pipeline
from agentic_blog.settings import DEFAULT_CONFIG_DIR, load_settings

app = typer.Typer(
    add_completion=False, help="Distil a source of knowledge once, render it many ways."
)
memory_app = typer.Typer(help="Inspect the per-topic memory.")
app.add_typer(memory_app, name="memory")


def _collect_sources(
    sources: list[str] | None,
    url: list[str],
    source_dir: Path | None,
    manifest: Path | None,
) -> list[str]:
    """Expand CLI source inputs into a flat origin list (shared by run + ingest).

    Combines positional paths/URLs, ``--url``, an optional recursed
    ``--source-dir``, and an optional ``--manifest``. Exits ``2`` on a bad
    directory or manifest path.
    """
    all_sources = list(sources or []) + list(url)
    if source_dir is not None:
        if not source_dir.is_dir():
            typer.secho(f"Not a directory: {source_dir}", fg=typer.colors.RED)
            raise typer.Exit(2)
        all_sources += _files_from_dir(source_dir)
    if manifest is not None:
        if not manifest.is_file():
            typer.secho(f"No such manifest file: {manifest}", fg=typer.colors.RED)
            raise typer.Exit(2)
        all_sources += _read_manifest(manifest)
    if not all_sources:
        typer.secho(
            "No sources given (paths, --url, --source-dir, or --manifest).",
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)
    return all_sources


@app.command()
def run(
    sources: list[str] = typer.Argument(None, help="File paths or URLs to ingest."),
    topic: str = typer.Option(..., "--topic", "-t", help="Topic slug for memory + output."),
    url: list[str] = typer.Option([], "--url", help="URL(s) to fetch and ingest."),
    source_dir: Path = typer.Option(
        None, "--source-dir", help="Directory to recurse for parseable files."
    ),
    manifest: Path = typer.Option(
        None, "--manifest", help="File listing sources (one path, folder, or URL per line)."
    ),
    render: str = typer.Option(
        None, "--render", "-r", help="Comma-separated renderers (default: config render.kinds)."
    ),
    debate: bool | None = typer.Option(
        None, "--debate/--no-debate", help="Override the config's debate panel setting."
    ),
    reingest: bool = typer.Option(
        False, "--reingest/--no-reingest", help="Force re-extraction of every source."
    ),
    config: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config", help="Config file or directory containing config.yaml."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Ingest → distil → render one topic."""
    configure_logging(verbose)
    all_sources = _collect_sources(sources, url, source_dir, manifest)

    renders = [r.strip() for r in render.split(",") if r.strip()] if render else None
    pipe = Pipeline.from_config(config)
    result = pipe.run(
        topic=topic, sources=all_sources, renders=renders, debate=debate, reextract=reingest
    )

    typer.secho(f"\nTopic:    {result.topic}", fg=typer.colors.GREEN)
    typer.echo(f"Output:   {result.topic_dir}")
    typer.echo(
        f"Score:    {result.score} (iterations: {result.iterations}, approved: {result.approved})"
    )
    typer.echo(f"Renders:  {', '.join(result.artifacts)}")
    if result.ingest_failures:
        typer.secho("Skipped sources:", fg=typer.colors.YELLOW)
        for failure in result.ingest_failures:
            typer.echo(f"  - {failure}")


def _files_from_dir(source_dir: Path) -> list[str]:
    """Return files under ``source_dir`` that a registered parser can handle."""
    registry = ParserRegistry()
    return sorted(
        str(p)
        for p in source_dir.rglob("*")
        if p.is_file() and registry.parser_for(str(p)) is not None
    )


def _read_manifest(manifest: Path) -> list[str]:
    """Expand a manifest file to a list of origins.

    Each non-empty, non ``#``-comment line is a URL, a file, or a directory.
    URLs pass through; directories are recursed (parseable files only); relative
    paths resolve against the manifest's own directory.
    """
    base = manifest.parent
    origins: list[str] = []
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if urlparse(line).scheme in {"http", "https"}:
            origins.append(line)
            continue
        target = Path(line)
        if not target.is_absolute():
            target = base / target
        if target.is_dir():
            origins += _files_from_dir(target)
        else:
            origins.append(str(target))
    return origins


@app.command()
def ingest(
    sources: list[str] = typer.Argument(None, help="File paths or URLs to ingest."),
    topic: str = typer.Option(..., "--topic", "-t", help="Topic slug for the raw/ output."),
    url: list[str] = typer.Option([], "--url", help="URL(s) to fetch and ingest."),
    source_dir: Path = typer.Option(
        None, "--source-dir", help="Directory to recurse for parseable files."
    ),
    manifest: Path = typer.Option(
        None, "--manifest", help="File listing sources (one path, folder, or URL per line)."
    ),
    reingest: bool = typer.Option(
        False, "--reingest/--no-reingest", help="Force re-extraction of every source."
    ),
    config: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config", help="Config file or directory containing config.yaml."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Ingest → extract → persist raw Markdown for a topic (no distill/render).

    Unchanged sources are reused from a prior ingest by default; pass
    ``--reingest`` to re-extract everything.
    """
    configure_logging(verbose)
    all_sources = _collect_sources(sources, url, source_dir, manifest)

    pipe = Pipeline.from_config(config)
    result = pipe.ingest(topic=topic, sources=all_sources, reextract=reingest)

    reused = set(result.reused)
    raw_by_id = {p.stem: p for p in result.raw_paths}
    for doc in result.documents:
        tag = "REUSE" if doc.origin in reused else "OK"
        typer.secho(f"{tag:<4} {doc.origin}", fg=typer.colors.GREEN)
        typer.echo(
            f"     parser={doc.metadata.get('parser')} "
            f"format={doc.metadata.get('format')} mime={doc.mime} chars={len(doc.text):,}"
        )
        typer.echo(f"     raw={raw_by_id.get(slugify(doc.source_id))}")
    for failure in result.failures:
        typer.secho(f"FAIL {failure.origin}", fg=typer.colors.YELLOW)
        typer.echo(f"     {failure.reason}")

    typer.secho(
        f"\n{len(result.extracted)} extracted, {len(result.reused)} reused, "
        f"{len(result.failures)} failed",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Raw Markdown under: {result.raw_dir}")


@app.command()
def distill(
    topic: str = typer.Option(..., "--topic", "-t", help="Topic slug to distill (reads raw/)."),
    debate: bool | None = typer.Option(
        None, "--debate/--no-debate", help="Override the config's debate panel setting."
    ),
    config: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config", help="Config file or directory containing config.yaml."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Reload a topic's raw/ Markdown and run distill only (no ingest/render)."""
    configure_logging(verbose)
    pipe = Pipeline.from_config(config)
    try:
        result = pipe.distill(topic=topic, debate=debate)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.secho(f"\nTopic:    {result.topic}", fg=typer.colors.GREEN)
    typer.echo(f"Sources:  {result.documents}")
    typer.echo(
        f"Score:    {result.score} (iterations: {result.iterations}, approved: {result.approved})"
    )
    typer.echo(f"Title:    {result.knowledge.title}")
    for path in result.output_paths:
        typer.echo(f"Wrote:    {path}")


@app.command()
def render(
    topic: str = typer.Option(
        ..., "--topic", "-t", help="Topic slug to render (reads distilled/)."
    ),
    renderers: str = typer.Option(
        None, "--render", "-r", help="Comma-separated renderers (default: config render.kinds)."
    ),
    config: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config", help="Config file or directory containing config.yaml."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Reload a topic's distilled knowledge and render artifacts (no ingest/distill)."""
    configure_logging(verbose)
    kinds = [r.strip() for r in renderers.split(",") if r.strip()] if renderers else None
    pipe = Pipeline.from_config(config)
    try:
        result = pipe.render(topic=topic, renders=kinds)
    except (FileNotFoundError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.secho(f"\nTopic:    {result.topic}", fg=typer.colors.GREEN)
    typer.echo(f"Output:   {result.topic_dir}")
    typer.echo(f"Renders:  {', '.join(result.artifacts)}")
    typer.echo(f"Sources:  {len(result.sources)}")
    for dest, status in result.statuses:
        color = {
            "created": typer.colors.GREEN,
            "updated": typer.colors.YELLOW,
            "unchanged": typer.colors.WHITE,
        }.get(status, typer.colors.WHITE)
        typer.secho(f"  {status:<9} {dest}", fg=color)
    typer.echo(f"Log:      {result.log_path}")


@app.command()
def check() -> None:
    """Report which optional extractors are installed."""
    typer.echo(format_report())


@memory_app.command("list")
def memory_list(
    config: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config", help="Config file or directory containing config.yaml."
    ),
) -> None:
    """List topics recorded in the output root."""
    root = load_settings(config).pipeline.output_root
    if not root.exists():
        typer.echo("No topics recorded yet.")
        return
    for topic_dir in sorted(p for p in root.iterdir() if (p / "index.yaml").exists()):
        data = yaml.safe_load((topic_dir / "index.yaml").read_text(encoding="utf-8")) or {}
        count = len(data.get("entries", []))
        typer.echo(f"- {topic_dir.name} ({count} source(s))")


@memory_app.command("show")
def memory_show(
    topic: str = typer.Argument(..., help="Topic to display."),
    config: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config", help="Config file or directory containing config.yaml."
    ),
) -> None:
    """Print a topic's human-readable memory index."""
    root = load_settings(config).pipeline.output_root
    index_md = root / slugify(topic) / "index.md"
    if not index_md.exists():
        typer.secho(f"No memory for topic {topic!r}.", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(index_md.read_text(encoding="utf-8"))


def main() -> None:  # pragma: no cover - entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
