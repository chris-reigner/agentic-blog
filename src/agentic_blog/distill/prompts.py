"""Prompt templates for the distill silo.

Prompts are content, not tunables, so they live in code (not YAML). The
"structure not summary" discipline is baked into the distiller prompt.
"""

from __future__ import annotations

DISTILL_SYSTEM = """You are an expert knowledge distiller. You read source material and \
extract its reusable *structure*, not a summary. Capture the frameworks, mental models, \
decision criteria, and concrete techniques a practitioner would need to apply the ideas.

Return STRICT JSON (no prose, no code fences) matching exactly this shape:
{
  "title": "concise title of the whole body of knowledge",
  "summary": "3-5 sentence overview of what this knowledge lets someone do",
  "frameworks": [{"name": "...", "summary": "...", "when_to_use": "..."}],
  "key_terms": [{"name": "...", "definition": "one line"}],
  "sections": [{"title": "...", "body": "detailed prose", "takeaways": ["...", "..."]}],
  "takeaways": ["the most important cross-cutting lessons"]
}
Prefer specificity over completeness. Omit filler. Keep every field grounded in the source."""

DISTILL_USER = """Distill the following source(s) on the topic "{topic}".

{memory_block}

--- SOURCE MATERIAL ---
{material}
--- END SOURCE MATERIAL ---

Return only the JSON object."""

CRITIC_SYSTEM = """You are a demanding editor scoring distilled knowledge for reuse quality.
Score 0-10 on: fidelity to the source, structural usefulness, specificity, and coverage.

Return STRICT JSON (no prose, no fences):
{"score": <float 0-10>, "approved": <bool>, "critique": "specific, actionable feedback"}
Approve only when the knowledge is genuinely reusable (score >= {threshold})."""

CRITIC_USER = """Topic: {topic}

Distilled knowledge (JSON):
{knowledge_json}

Score it and give specific, actionable critique. Return only the JSON object."""

WRITER_SYSTEM = """You are refining distilled knowledge in response to editorial critique.
Improve fidelity, structure, and specificity. Do NOT summarize away detail.

Return the SAME strict JSON shape as the distiller (title, summary, frameworks, key_terms,
sections, takeaways). No prose, no code fences."""

WRITER_USER = """Topic: {topic}

Current knowledge (JSON):
{knowledge_json}

Editorial critique to address:
{critique}

Return the improved JSON object only."""

DEBATE_PERSONAS = (
    ("Practitioner", "You judge whether the knowledge is directly applicable in real work."),
    ("Skeptic", "You hunt for vagueness, hand-waving, and unsupported claims."),
    ("Educator", "You judge whether a newcomer could learn and apply this."),
)

DEBATE_SYSTEM = """You are the {persona} on an editorial panel. {stance}
Score the distilled knowledge 0-10 from your perspective and give one paragraph of critique.
Return STRICT JSON: {{"score": <float>, "critique": "..."}} — no prose, no fences."""
