"""Optional-extractor probing and a ``check`` report.

Each format degrades to a stdlib fallback when its best tool is missing; this
module reports what is installed so users can improve extraction quality.
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

# import name -> pip package
PYTHON_DEPENDENCIES: dict[str, str] = {
    "pymupdf4llm": "pymupdf4llm",
    "pypdf": "pypdf",
    "pdfminer": "pdfminer.six",
    "bs4": "beautifulsoup4",
    "markdownify": "markdownify",
    "docx": "python-docx",
    "striprtf": "striprtf",
}

# format label -> (probe kind, name, pip/how-to)
_FORMAT_TOOLS: dict[str, list[tuple[str, str, str]]] = {
    "pdf": [
        ("py", "pymupdf4llm", "pip install pymupdf4llm  (Markdown output)"),
        ("cli", "pdftotext", "poppler-utils (apt install poppler-utils / brew install poppler)"),
        ("py", "pypdf", "pip install pypdf"),
        ("py", "pdfminer", "pip install pdfminer.six"),
    ],
    "docx": [("py", "docx", "pip install python-docx")],
    "html/url": [
        ("py", "bs4", "pip install beautifulsoup4"),
        ("py", "markdownify", "pip install markdownify  (Markdown output)"),
    ],
    "github": [("cli", "git", "install git — https://git-scm.com/downloads")],
    "rtf": [("py", "striprtf", "pip install striprtf")],
}


def has_python_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def has_cli(name: str) -> bool:
    return shutil.which(name) is not None


@dataclass(frozen=True, slots=True)
class ToolStatus:
    fmt: str
    name: str
    kind: str
    installed: bool
    how_to_install: str


def probe() -> list[ToolStatus]:
    """Report the install status of every known extractor."""
    out: list[ToolStatus] = []
    for fmt, tools in _FORMAT_TOOLS.items():
        for kind, name, how in tools:
            installed = has_cli(name) if kind == "cli" else has_python_module(name)
            out.append(ToolStatus(fmt, name, kind, installed, how))
    return out


def format_report() -> str:
    """Human-readable ``check`` report."""
    lines = ["Extractor availability (best tool first per format):", ""]
    current = ""
    for st in probe():
        if st.fmt != current:
            lines.append(f"[{st.fmt}]")
            current = st.fmt
        mark = "OK " if st.installed else "-- "
        tail = "" if st.installed else f"   → {st.how_to_install}"
        lines.append(f"  {mark} {st.name} ({st.kind}){tail}")
    return "\n".join(lines)
