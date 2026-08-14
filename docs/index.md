# agentic-blog

**Distil a source of knowledge once, then render it many ways** — a Markdown
article, a blog post, a LinkedIn post, or an agent **skill** (`SKILL.md`). The
skill is not special; it is one renderer among several, all drawing from the same
distilled `Knowledge`.

## How it works

A run is a small state machine with hard boundaries between silos, communicating
only through contracts (`RawDocument` → `Knowledge` → `Artifact`):

```
ingest → memory → distill → render → memory
```

## Documentation

- [Pipeline](PIPELINE.md) — the end-to-end run and orchestration.
- [Ingest](INGEST.md) — turning sources into `RawDocument`s.
- [Distill](DISTILL.md) — producing the shared `Knowledge` object.
- [Render](RENDER.md) — emitting Markdown, blog, LinkedIn, and skill artifacts.
- [Memory](MEMORY.md) — the per-topic editorial memory.

## Quick start

```bash
make install
make run ARGS="run book.pdf --topic obs --render blog,skill"
```
