"""agentic-blog — distil a source of knowledge once, render it many ways.

Public library surface::

    from agentic_blog import Pipeline, load_settings
    pipe = Pipeline.from_config("config/")
    result = pipe.run(topic="observability", sources=["book.pdf"], renders=["blog", "skill"])
"""

from __future__ import annotations

from agentic_blog.contracts import (
    Artifact,
    Framework,
    Knowledge,
    RawDocument,
    Section,
    Term,
)
from agentic_blog.pipeline import Pipeline, RunResult
from agentic_blog.settings import Settings, load_settings

__version__ = "0.1.0"

__all__ = [
    "Artifact",
    "Framework",
    "Knowledge",
    "Pipeline",
    "RawDocument",
    "RunResult",
    "Section",
    "Settings",
    "Term",
    "load_settings",
    "__version__",
]
