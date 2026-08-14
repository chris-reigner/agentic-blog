# agentic-blog

**Distil a source of knowledge once, then render it many ways** — a Markdown
article, a blog post, a LinkedIn post, or an agent **skill** (`SKILL.md`). The
skill is not special; it is one renderer among several, all drawing from the same
distilled `Knowledge`.

A simplified fork of [AgenticBlog](https://github.com/Tutanka01/AgenticBlog),
keeping its LangGraph orchestration and Markdown-first editorial memory, adding a
book-to-skill–style parser front-end and a render-agnostic core.

## How it works

```
files + URLs ──▶ INGEST ──▶ DISTILL ──▶ RENDER ──▶ per-topic output/
                 parsers    writer/     markdown | blog | linkedin | skill
                            critic
                       MEMORY (per topic, Markdown-first)
```

Four silos with hard boundaries, talking only through the contracts in
`agentic_blog/contracts.py` (`RawDocument` → `Knowledge` → `Artifact`). A run is
a LangGraph state machine: `ingest → memory → distill → render → memory`.

## Install

```bash
make install                 # editable install + extractors + dev tools + hooks
cp .env.example .env         # set LLM_API_KEY (only for hosted LLMs)
```

## Use

```bash
# full pipeline: ingest → distil → render
agentic-blog run ./book.pdf --topic observability --render blog,skill

# or run the stages independently (each reloads the previous stage's output)
agentic-blog ingest  --topic tfm --manifest resources/tfm.txt
agentic-blog distill --topic tfm
agentic-blog render  --topic tfm --render blog,skill
```

```python
from agentic_blog import Pipeline

pipe = Pipeline.from_config("config/")
result = pipe.run(topic="observability", sources=["book.pdf"], renders=["blog", "skill"])
print(result.topic_dir)      # output/observability/
```

All tunables live in one `config/config.yaml` (a section per silo); secrets come
from `.env`. Defaults target a local Ollama LLM, so `run`/`distill` work with no
API key.

## Documentation

- **[Pipeline](docs/PIPELINE.md)** — the graph, state, checkpointing, and CLI/library surface.
- **[Ingest](docs/INGEST.md)** · **[Distill](docs/DISTILL.md)** · **[Render](docs/RENDER.md)** · **[Memory](docs/MEMORY.md)** — per-silo guides, config, and internals.

## Development

```bash
make lint      # ruff + yamllint
make type      # mypy --strict
make test      # pytest + coverage
make check     # all three (what CI runs)
```

## Backlog

- Test clean all
- Improve rendering artefacts to specific format
- Test parsers for multiple sources
- Add images parsers to keep important images
- Improve critics behaviour
- Improve memory optimization
- create plugin for claude code
- test with ml-engineering for grpo skills
