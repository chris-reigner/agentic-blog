# agentic-blog — Design & Architecture (for validation)

> **Status:** proposal, awaiting sign-off. No implementation code exists yet.
> This document is the contract we agree on *before* writing a line of the package.

## 1. What this is

A simplified fork of [AgenticBlog](https://github.com/Tutanka01/AgenticBlog) built around
one idea: **distil a source of knowledge once, then render it many ways.**

A "render" is any consumable artifact — a Markdown article, a blog post, a LinkedIn
post, or an **agent skill** (`SKILL.md` + companion files). The skill is *not* special;
it is one renderer among several. The distilled knowledge in the middle is
render-agnostic, and every renderer draws from the **same `Knowledge`** but uses a
different slice of it at a different compression (see §3.3).

Three things carry over from the original, deliberately:
1. The **LangGraph** multi-agent orchestration (simplified graph, checkpoint/resume kept).
2. The **Markdown-first memory** — the crown jewel. Human- and machine-readable, no
   vector DB *required*. Organized **per topic** (like research-ops), read before
   distillation and updated after rendering. The storage backend is **pluggable** so a
   knowledge-base / vector / graph store can replace Markdown later without touching
   callers (see §3.4).
3. The **write → critique → revise** quality loop, with an **optional multi-persona
   debate panel** (off by default, one flag to enable).

Explicitly **cut for now** (seams left open):
- Research-ops / deep web research. The ingest silo leaves a `Parser`-Protocol seam and
  the memory layout is intentionally research-ops-compatible so this drops in later.
- The RSS scraper → filter → selector discovery front-end.

## 2. Design goals & non-goals

**Goals**
- **Silos with hard boundaries.** Ingest, distillation, rendering, and memory are
  independent packages that talk through explicit contracts, not shared internals.
- **Render-agnostic core.** Adding a new output format (e.g. a slide deck) must not touch
  ingest, distillation, or memory.
- **Pluggable memory backend.** Markdown-first, but `MemoryStore` is a Protocol; a
  knowledge-base backend is an additive implementation.
- **Usable as a library, not just a CLI.** A public Python API (`from agentic_blog import
  Pipeline`) that a notebook, a service, or a future research-ops front-end can call.
- **Output organized per topic** — one self-contained directory per topic/run, mirroring
  research-ops' research-directory model.
- **Config in YAML, not in code.** All tunables live in versioned YAML files; code reads
  them through a typed settings layer. No magic numbers scattered in modules.
- **Quality gates built in.** Linters, type-checkers, formatters, and tests wired into a
  task runner + pre-commit + CI from day one.
- **SOLID + PEP-compliant.** Small single-responsibility modules, dependency inversion via
  `Protocol`s, typed frozen dataclasses / Pydantic models as the inter-silo contracts.

**Non-goals (now)**
- Web research / crawling beyond a single user-supplied URL.
- A UI (the original ships Streamlit + FastAPI). CLI + library first; API is a later concern.
- Multi-language output parity — keep the `--lang` hook but don't over-invest.

## 3. Silo architecture

Four independent silos + a thin orchestration layer. Arrows are **data contracts**, not
imports of internals.

```
                          ┌──────────────────────────────────────────────┐
                          │                 MEMORY (silo)                  │
                          │  Per-topic. Read before, write after.          │
                          │  MemoryStore Protocol:                         │
                          │    • MarkdownStore  (default, no DB)           │
                          │    • KnowledgeBaseStore (future: vector/graph) │
                          └──────────────┬───────────────▲─────────────────┘
                                 read ctx │               │ record run
                                          ▼               │
  ┌───────────┐   RawDocument   ┌───────────────┐  Knowledge  ┌───────────────┐  Artifact
  │  INGEST   │────────────────▶│  DISTILLATION │────────────▶│   RENDERING   │──────────▶ topic dir
  │  (silo)   │                 │    (silo)     │             │    (silo)     │
  │ parsers/  │                 │ writer+critic │             │ renderers/    │
  └───────────┘                 │ (+debate opt) │             └───────────────┘
   files + 1 URL                 └───────────────┘             markdown | blog |
                                          ▲                    linkedin | skill
                                          │ orchestrated by       (share Knowledge,
                                 ┌────────┴─────────┐             differ in slice+compression)
                                 │  ORCHESTRATION   │  LangGraph: build_graph(),
                                 │   (graph.py)     │  PipelineState, SQLite checkpointer
                                 └──────────────────┘
                                          ▲
                                          │ configured by
                                 ┌────────┴─────────┐
                                 │  config/*.yaml   │  pipeline · llm · feeds ·
                                 │  (versioned)     │  render · memory · debate
                                 └──────────────────┘
```

### 3.1 Ingest silo — `agentic_blog/ingest/`
Turns *any* source into a normalized `RawDocument`. This is the transplanted
book-to-skill parser layer, kept as an **independent sub-package** with zero knowledge
of skills, blogs, or LangGraph.

- `parsers/` — one module per format: `pdf.py`, `docx.py`, `html.py`,
  `rtf.py`, `github.py`, `text.py`, `url.py`. Best-tool-first, stdlib fallback.
- `registry.py` — maps extension/scheme → parser via a `Parser` `Protocol`
  (Open/Closed: add a format by adding a module + registering it, no edits elsewhere).
- `dependencies.py` — optional-dep probing + `--check` (from book-to-skill).
- `sanitize.py` — Unicode scrubbing / invisible-char removal (from book-to-skill).
- `service.py` — `IngestService.load(sources) -> list[RawDocument]`; batch-tolerant
  (one bad source is skipped with a warning, per the original's "graceful degradation").

**URL fetch** is just another parser (`url.py`) — a single direct fetch + HTML clean,
lifted from AgenticBlog's `fetcher.py`. This is the seam where research-ops plugs in
later: swap `url.py` for a richer research provider behind the same `Parser` Protocol.

**Contract out:** `RawDocument { source_id, origin, mime, title?, text, metadata }`.
`source_id` is derived from the origin path/URL and serves as the **dedup key** shared
with the memory silo (matches research-ops' `original_path` dedup).

### 3.2 Distillation silo — `agentic_blog/distill/`
Turns `RawDocument`(s) + memory context into render-agnostic `Knowledge`.

- `distiller.py` — one deep pass: extract structure (frameworks, key points, sections,
  glossary-worthy terms) into a `Knowledge` object. "Structure not summary" discipline
  from book-to-skill, produced by an LLM node.
- `writer.py` / `critic.py` — the quality loop. `writer` drafts/refines the `Knowledge`
  narrative; `critic` scores it; loop until approved or `max_iterations` (from YAML).
- `debate.py` — **optional** multi-persona debate panel (ported from AgenticBlog's
  `multi_critic`). Enabled via `debate.enabled: true` in config or `--debate`; when off,
  a single critic runs. `num_personas` / `rounds` come from YAML.
- `models.py` — `Section`, `Framework`, `Term` (the pieces of `Knowledge`).

**Contract out:** `Knowledge` — a structured, format-neutral representation.
**Nothing here knows what the final artifact will be.**

### 3.3 Rendering silo — `agentic_blog/render/`
Turns one `Knowledge` into one or more `Artifact`s. **This is where "skill is just a
renderer" lives — and where the shared-knowledge / different-slice principle is made
concrete.**

All renderers consume the **same** `Knowledge`. They differ in *which fields* they read
and *how hard they compress*:

| Renderer | Slice of `Knowledge` used | Compression / shape |
|----------|---------------------------|---------------------|
| `markdown.py` | sections + takeaways | low — full long-form prose |
| `blog.py` | summary + top sections + SEO front-matter | medium — narrative, ~900–1200 words |
| `linkedin.py` | summary + top 3 takeaways | high — hook + 3 points + hashtags |
| `skill.py` | frameworks + sections + key_terms + takeaways | structural — `SKILL.md` (front-loaded ~4k tok) + `chapters/*.md` (on-demand) + `glossary.md` + `cheatsheet.md` |

- `base.py` — `Renderer` `Protocol`: `render(knowledge: Knowledge) -> Artifact`, plus a
  `RenderPolicy` (target length / compression) each renderer applies.
- `registry.py` — `--render markdown,skill` selects renderers (Open/Closed again).

**Contract out:** `Artifact { kind, files: {relpath: content}, summary }`.

### 3.4 Memory silo — `agentic_blog/memory/`
The crown jewel, promoted to a first-class silo with a **pluggable backend** and a
**per-topic** layout aligned with research-ops.

- `store.py` — `MemoryStore` `Protocol`: the backend seam.
  - `MarkdownStore` (default) — pure Markdown + a canonical YAML index. No DB.
  - `KnowledgeBaseStore` (future) — vector/graph/RAG backend; additive, same Protocol.
- `wiki.py` — `Memory` façade over a `MemoryStore`, with two roles:
  - **read:** `context_for(topic, sources) -> MemoryContext` — recent topics (novelty
    window), related past entries, and re-injected "lessons" from prior low-scoring runs.
    Injected into the distiller/writer.
  - **write:** `record(topic, run) -> None` — upsert a per-source entry, update the topic
    index, append lessons when a run needed ≥2 critic iterations.
- `models.py` — `MemoryContext`, `MemoryEntry`.

**Per-topic, research-ops-compatible layout** (see §5 for where it lives on disk). One
directory per topic; within it, memory is keyed **per source** for dedup:

```
<topic-slug>/
  index.yaml            # canonical catalog (dedup key = source_id); machine source of truth
  index.md              # human-readable regeneration of the catalog
  entries/<source-slug>.md   # one page per source ingested
  lessons.md            # re-injected editorial lessons from low-scoring runs
  log.md                # append-only run log
```

`index.yaml` is authoritative (mirrors research-ops: YAML canonical, `index.md`
regenerated). Sources already in `index.yaml` are **skipped** on re-ingest.

**Why a silo:** memory is read by distillation *and* informs rendering, and is written
after rendering. A package with a clean Protocol keeps this cross-cutting concern from
leaking into every node — and makes the Markdown→KB swap a one-line wiring change.

### 3.5 Orchestration — `agentic_blog/graph.py` + `state.py`
LangGraph, simplified. Retains `PipelineState` (TypedDict) and the SQLite checkpointer
for resumable runs. Nodes are thin adapters that call into the silos:

```
ingest → memory.read → distill → critic ─(loop)─ writer → [debate?] → render → memory.write → END
                                    └──────────approved───────────────┘
```

Removed vs. original: `scraper`, `filter`, `selector`. Kept/renamed: `fetcher`→ingest,
`writer`+`critic` (distill), optional `debate`, `formatter`→render,
`output_saver`→ split into render (files) + memory.write.

## 4. Core contracts (the inter-silo types)

Defined once in `agentic_blog/contracts.py`, imported by all silos. These are the only
things silos share — everything else is private.

```python
@dataclass(frozen=True)
class RawDocument:
    source_id: str            # stable dedup key (path/url hash) — shared with memory
    origin: str               # file path or URL
    mime: str
    text: str                 # extracted, sanitized plain text
    title: str | None
    metadata: Mapping[str, object]

@dataclass(frozen=True)
class Knowledge:              # render-agnostic distilled output; shared by ALL renderers
    title: str
    summary: str
    sections: Sequence[Section]      # ordered; ~ chapters
    frameworks: Sequence[Framework]  # named, with "when to use"
    key_terms: Sequence[Term]        # glossary-worthy
    takeaways: Sequence[str]
    provenance: Sequence[str]        # source_ids that fed this
    metadata: Mapping[str, object]

@dataclass(frozen=True)
class Artifact:
    kind: str                        # "markdown" | "blog" | "linkedin" | "skill"
    files: Mapping[str, str]         # relpath -> content
    summary: str
```

`Parser`, `Renderer`, and `MemoryStore` are `typing.Protocol`s — the dependency-inversion
seams. Concretions are wired at the edges (registry/CLI); the orchestrator depends on the
Protocol, never the concretion. LLM access goes through an `llm` wrapper so tests inject a fake.

## 5. Proposed repository layout

```
agentic-blog/
├── pyproject.toml                 # hatchling · ruff · mypy · pytest · optional-deps per format
├── README.md
├── Makefile                       # task automation (see §7)
├── .pre-commit-config.yaml        # ruff, ruff-format, mypy, end-of-file, yaml-lint
├── .env.example                   # secrets only (API keys) — NOT tunables
├── config/                        # ← all tunables live here, versioned, YAML (§6)
│   └── config.yaml                # one file; top-level section per silo:
│                                  #   pipeline · llm · render · memory · debate
├── docs/
│   ├── DESIGN.md                  # this file
│   └── ARCHITECTURE.md            # (generated after sign-off)
├── src/
│   └── agentic_blog/
│       ├── __init__.py            # public API: Pipeline, run(), version (library surface)
│       ├── py.typed
│       ├── contracts.py           # RawDocument, Knowledge, Artifact, Protocols
│       ├── settings.py            # Pydantic models that LOAD the config/*.yaml (§6)
│       ├── llm.py                 # OpenAI-compatible client wrapper
│       ├── graph.py               # LangGraph build_graph()
│       ├── state.py               # PipelineState (TypedDict)
│       ├── pipeline.py            # high-level façade for library use (§8)
│       ├── cli.py                 # `agentic-blog` entrypoint (typer)
│       ├── ingest/
│       │   ├── service.py  registry.py  dependencies.py  sanitize.py
│       │   └── parsers/           # pdf docx html rtf github text url
│       ├── distill/
│       │   ├── distiller.py  writer.py  critic.py  debate.py  models.py
│       ├── render/
│       │   ├── base.py            # Renderer Protocol + RenderPolicy + registry
│       │   ├── markdown.py  blog.py  linkedin.py  skill.py
│       └── memory/
│           ├── wiki.py            # Memory façade (read + write)
│           ├── store.py           # MemoryStore Protocol + MarkdownStore (+ KB stub)
│           └── models.py
├── tests/
│   ├── ingest/  distill/  render/  memory/     # mirror the package
│   └── conftest.py                # fakes/fixtures for LLM + filesystem
├── tools/                         # author/CI-only helpers — NEVER bundled into artifacts
│   └── validate_skill.py          # lints a GENERATED SKILL.md; runs in our CI only
└── output/                        # runtime, per-topic dirs (gitignored) — see §8
    └── <topic-slug>/
        ├── index.yaml  index.md  log.md  lessons.md
        ├── entries/<source-slug>.md          # memory pages (per source)
        └── artifacts/                         # rendered outputs
            ├── blog_post.md  linkedin_post.md
            └── skill/ (SKILL.md, chapters/, glossary.md, cheatsheet.md)
```

**Memory + artifacts share the per-topic directory** so a topic is one self-contained,
inspectable folder — exactly the research-ops "research directory" ergonomic.

## 6. Configuration — YAML first, no in-code tunables

Rule: **secrets** go in `.env` (API keys); **everything else** is a YAML file in
`config/`, loaded once into typed Pydantic `BaseSettings` models in `settings.py`. No
module hard-codes a threshold, model name, path, or count.

```yaml
# config/config.yaml — one file, one top-level section per silo.
pipeline:
  max_critique_iterations: 3
  approval_threshold: 8
  novelty_window_days: 14
  output_root: ./output

llm:
  base_url: http://localhost:11434/v1
  model: gpt-oss:20b
  temperature: 0.3
  timeout_seconds: 600
  debate_model: null          # falls back to `model`

render:
  markdown: {compression: low}
  blog:     {compression: medium, target_words: 1100, seo: true}
  linkedin: {compression: high, hashtags: 3}
  skill:    {compression: structural, skill_md_max_tokens: 4000, chapter_budget_tokens: 1200}

memory:
  backend: markdown           # markdown | knowledge_base
  novelty_window_days: 14
  max_lessons_injected: 5

debate:
  enabled: false              # optional; --debate flips it on
  num_personas: 3
  rounds: 2
```

`settings.py` supports env-var overrides (12-factor) and validates on load, so a bad
config fails fast with a clear error instead of a mid-run surprise.

## 7. Quality gates & task automation

**Linters / checkers (wired in `pyproject.toml` + `.pre-commit-config.yaml`):**
- `ruff` — lint (pyflakes, pycodestyle, isort, bugbear, pyupgrade) + `ruff format`.
- `mypy --strict` — full static typing on `src/` (contracts make this tractable).
- `yamllint` — validates `config/*.yaml`.
- `pytest` + `pytest-cov` — per-silo unit tests; coverage floor in CI.
- `pip-audit` (optional) — dependency CVE check.

**Task automation — `Makefile` (single entrypoint for humans and CI):**

```
make install     # uv/pip install -e ".[all,dev]" + pre-commit install
make lint         # ruff check + yamllint
make format       # ruff format
make type         # mypy --strict src
make test         # pytest -q --cov
make check        # lint + type + test   (what CI runs, and pre-push)
make run TOPIC=...  ARGS=...             # convenience wrapper over the CLI
```

**CI (`.github/workflows/ci.yml`):** matrix over supported Pythons → `make check`.
`pre-commit` mirrors the fast subset so issues are caught before commit.

**Skill-tooling boundary (carried from the book-to-skill critique):** author/CI tools
(e.g. `tools/validate_skill.py`) live in *our* repo and run in *our* CI. They are
**never** copied into a generated skill artifact. Only genuine runtime helpers a
generated skill shells out to get bundled into `Artifact.files`. Any skill security scan
is an **optional** render-time gate, off by default.

## 8. Using it as a library + per-topic output

The package is designed to be imported, not only shelled out to. A future research-ops
front-end will call this exact surface.

```python
from agentic_blog import Pipeline

pipe = Pipeline.from_config("config/")           # loads YAML settings
result = pipe.run(
    topic="observability",
    sources=["./book.pdf", "https://example.com/post"],
    renders=["blog", "skill"],
    debate=False,
)
# result.topic_dir -> output/observability/
# result.artifacts -> {"blog": Artifact, "skill": Artifact}
# memory for the topic is read before and updated after, automatically
```

Every run resolves to a **per-topic directory** under `output/<topic-slug>/` holding both
the memory layer (`index.yaml`, `entries/`, `lessons.md`, `log.md`) and the rendered
`artifacts/`. Re-running the same topic **appends** (dedup by `source_id`), so the topic
folder grows into a durable, self-contained knowledge base — the research-ops model.

## 9. CLI surface (first cut, thin wrapper over the library)

```bash
agentic-blog run ./book.pdf ./notes.md --topic observability --render blog,skill
agentic-blog run --url https://example.com/post --topic obs --render markdown --debate
agentic-blog check                # optional-extractor / env report (from book-to-skill)
agentic-blog memory list          # list topics + sources in output/
agentic-blog memory show observability
```

## 10. Applying SOLID & PEP

- **SRP** — one parser per format; one renderer per artifact; memory read/write separate;
  nodes are thin adapters; config loading isolated in `settings.py`.
- **OCP** — new formats, renderers, and memory backends register via a Protocol + registry;
  orchestrator and contracts stay untouched.
- **LSP** — every `Parser`→valid `RawDocument`, every `Renderer`→valid `Artifact`, every
  `MemoryStore` interchangeable; no special-casing.
- **ISP** — narrow Protocols (`Parser.parse`, `Renderer.render`, `MemoryStore.read/append`).
- **DIP** — silos depend on `contracts.py` abstractions; concretions wired at edges;
  memory backend chosen from the `memory:` section of `config/config.yaml`.
- **PEP 8 / 484 / 561** — `src/` layout, full hints, `py.typed`, ruff + mypy, frozen
  dataclasses for value objects, Google-style docstrings.
- **12-factor config** — YAML in `config/`, env overrides, secrets in `.env`, validated on load.

## 11. Dependencies (lean)

- **Core:** `langgraph`, `langgraph-checkpoint-sqlite`, `pydantic`, `pydantic-settings`,
  `httpx`, `beautifulsoup4`, `pyyaml`, `typer`, an OpenAI-compatible client.
- **Optional per format (extras):** `pymupdf4llm`/`pypdf`/`pdfminer.six` (pdf),
  `markdownify` (html/url), `python-docx` (docx), `striprtf` (rtf).
- **Dev:** `pytest`, `pytest-cov`, `ruff`, `mypy`, `yamllint`, `pre-commit`.

## 12. Migration plan (once signed off)

1. Scaffold `src/agentic_blog/`, `pyproject.toml`, `config/*.yaml`, `settings.py`,
   `contracts.py`, `Makefile`, `.pre-commit-config.yaml`, CI, tests skeleton.
2. Port **parsers** from book-to-skill into `ingest/` (adapt to `Parser` + `RawDocument`);
   port `url.py` from AgenticBlog's `fetcher.py`.
3. Build **memory** silo: `MemoryStore` Protocol + `MarkdownStore` + per-topic layout;
   stub `KnowledgeBaseStore`. Port AgenticBlog's memory logic.
4. Build **distill**: distiller + writer/critic loop + optional debate + `Knowledge`.
5. Build **render**: `markdown` + `skill` first, then `blog` + `linkedin`, each with its
   `RenderPolicy` compression.
6. Wire simplified `graph.py`; add `pipeline.py` (library façade) + `cli.py`; tests per silo.

## 13. Decisions locked in (from validation)

- Package `agentic_blog` under `src/`. ✅
- Skill and blog **share one `Knowledge`**, differ in slice + compression (§3.3). ✅
- Memory is **per source/topic**, research-ops-compatible layout (§3.4). ✅
- LangGraph **checkpoint/resume** kept. ✅
- Debate panel **kept but optional** (`debate:` in `config/config.yaml`, `--debate`). ✅
- Memory **Markdown-first** with a **pluggable `MemoryStore`** for a future KB. ✅
- Linters/checkers + **task automation** + **YAML config** (§6, §7). ✅
- Designed for **library use** with **per-topic output folders** (§8). ✅

## 14. Critique boundary (decided — simplest approach)

- **Critique happens once, during distillation, on the shared `Knowledge`.** There is
  **no per-rendered-artifact critic loop.** The `writer → critic → revise` cycle scores
  and refines the `Knowledge`/draft; once approved, every renderer (markdown, blog,
  linkedin, skill) draws from that already-validated `Knowledge`. Renderers are
  deterministic transforms, not separately critiqued. This is the leanest design and
  keeps quality centralized in one place. ✅
```
