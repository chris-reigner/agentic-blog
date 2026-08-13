"""Central logging setup — colored, per-silo console logging via Rich.

One :func:`configure_logging` call (from the CLI entry) installs a single
``RichHandler`` on stderr, tags every record with its silo (``ingest``,
``distill``, ``render``, ``memory``, …) derived from the logger name, and quiets
noisy third-party libraries. Application code just uses
``logging.getLogger(__name__)`` as usual.
"""

from __future__ import annotations

import contextlib
import logging

from rich.console import Console
from rich.logging import RichHandler

_APP_LOGGER = "agentic_blog"

# Third-party loggers pinned to WARNING so their INFO/DEBUG chatter stays hidden.
_NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "openai", "pymupdf", "fontTools")


class _SiloFilter(logging.Filter):
    """Attach a short silo tag to each record, derived from its logger name.

    ``agentic_blog.ingest.service`` -> ``[ingest]``; anything outside the app
    package keeps its top-level module name.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        parts = record.name.split(".")
        silo = parts[1] if parts[0] == _APP_LOGGER and len(parts) >= 2 else parts[0]
        record.silotag = f"[{silo}]"
        return True


def _route_pymupdf_messages() -> None:
    """Route pymupdf/pymupdf4llm chatter into the ``pymupdf`` logger.

    pymupdf4llm flushes an OCR/parser banner via ``pymupdf.message``. Sending it
    through Python logging (rather than disabling it) keeps the OCR path working
    while the WARNING pin on the ``pymupdf`` logger hides the INFO-level banner.
    """
    try:
        import pymupdf
    except ImportError:
        return
    # older/newer pymupdf without the kwarg — best effort
    with contextlib.suppress(Exception):
        pymupdf.set_messages(pylogging_level=logging.DEBUG)  # type: ignore[no-untyped-call]


def configure_logging(verbose: bool = False) -> None:
    """Install the Rich console handler. Idempotent; safe to call more than once.

    ``verbose`` bumps the app's own loggers to DEBUG; otherwise they log at INFO.
    Third-party loggers stay at WARNING regardless.
    """
    handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
        show_path=False,
        markup=False,
        omit_repeated_times=False,
    )
    handler.addFilter(_SiloFilter())
    handler.setFormatter(logging.Formatter("%(silotag)-9s %(message)s"))

    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.WARNING)

    logging.getLogger(_APP_LOGGER).setLevel(logging.DEBUG if verbose else logging.INFO)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _route_pymupdf_messages()
