"""GitHub repository parser: shallow-clone a repo and flatten it to Markdown.

A ``github.com/<owner>/<repo>`` URL is cloned with ``git clone --depth=1`` into a
reusable sibling cache, then reduced to one Markdown digest — a file tree, the
README, and the text/source files (size-capped). Richer per-module curation is a
distillation concern and stays out of the ingest silo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse

from agentic_blog.contracts import RawDocument
from agentic_blog.ingest.parsers._textio import read_text_file
from agentic_blog.ingest.parsers.base import ExtractionError, source_id_for

_CLONE_TIMEOUT = 120
_MAX_TREE_ENTRIES = 500
_MAX_FILE_CHARS = 20_000
_MAX_TOTAL_CHARS = 200_000

# Text/source files worth inlining. Anything else (binaries, media) is skipped.
_TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cs",
        ".php",
        ".scala",
        ".kt",
        ".swift",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".r",
        ".jl",
        ".lua",
        ".pl",
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".cfg",
        ".ini",
        ".proto",
        ".gradle",
    }
)
_SKIP_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "cargo.lock",
        "uv.lock",
        "composer.lock",
        "gemfile.lock",
    }
)
# Roughly map suffix -> fence language for readable code blocks.
_FENCE_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
}


def _run_git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_CLONE_TIMEOUT,
        encoding="utf-8",
        errors="replace",
    )


class GithubParser:
    """Clones a GitHub repo (shallow) and renders it as a single Markdown digest."""

    def __init__(self, cache_dir: Path | str = ".github-cache") -> None:
        self._cache_dir = Path(cache_dir)

    def can_parse(self, origin: str) -> bool:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
            return False
        parts = [p for p in parsed.path.split("/") if p]
        return len(parts) >= 2

    def _resolve(self, origin: str) -> tuple[str, str, str | None]:
        parts = [p for p in urlparse(origin).path.split("/") if p]
        owner, repo = parts[0], parts[1].removesuffix(".git")
        branch = parts[3] if len(parts) >= 4 and parts[2] == "tree" else None
        return owner, repo, branch

    def parse(self, origin: str) -> RawDocument:
        import shutil

        if not shutil.which("git"):
            raise ExtractionError("git is required to ingest GitHub repos (install git).")

        owner, repo, branch = self._resolve(origin)
        clone_path = self._cache_dir / f"{owner}-{repo}"
        clone_url = f"https://github.com/{owner}/{repo}.git"

        if not (clone_path / ".git").is_dir():
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            cmd = ["clone", "--depth=1"]
            if branch:
                cmd += ["--branch", branch]
            cmd += [clone_url, str(clone_path)]
            result = _run_git(cmd)
            if result.returncode != 0:
                raise ExtractionError(f"git clone failed for {origin}: {result.stderr.strip()}")

        sha = _run_git(["rev-parse", "HEAD"], cwd=str(clone_path))
        commit_sha = sha.stdout.strip() if sha.returncode == 0 else "unknown"

        ls = _run_git(["ls-files"], cwd=str(clone_path))
        files = [f for f in ls.stdout.splitlines() if f] if ls.returncode == 0 else []

        text = self._build_digest(owner, repo, clone_url, commit_sha, branch, clone_path, files)
        return RawDocument(
            source_id=source_id_for(origin),
            origin=origin,
            mime="text/markdown",
            text=text,
            title=f"{owner}/{repo}",
            metadata={
                "parser": "git-clone",
                "format": "markdown",
                "commit_sha": commit_sha,
                "branch": branch or "",
                "file_count": len(files),
            },
        )

    def _build_digest(
        self,
        owner: str,
        repo: str,
        clone_url: str,
        commit_sha: str,
        branch: str | None,
        clone_path: Path,
        files: list[str],
    ) -> str:
        parts: list[str] = [
            f"# {owner}/{repo}",
            "",
            f"- Repository: {clone_url}",
            f"- Commit: `{commit_sha}`",
            f"- Branch: {branch or '(default)'}",
            f"- Files: {len(files)}",
            "",
            "## File tree",
            "",
        ]
        for path in files[:_MAX_TREE_ENTRIES]:
            parts.append(f"- `{path}`")
        if len(files) > _MAX_TREE_ENTRIES:
            parts.append(f"- … {len(files) - _MAX_TREE_ENTRIES} more")
        parts.append("")

        readme = self._read_readme(clone_path, files)
        if readme:
            parts += ["## README", "", readme, ""]

        parts.append("## Source files")
        parts.append("")
        budget = _MAX_TOTAL_CHARS
        for path in files:
            name = Path(path).name.lower()
            suffix = Path(path).suffix.lower()
            if name in _SKIP_NAMES or suffix not in _TEXT_SUFFIXES:
                continue
            if suffix in {".md", ".markdown", ".rst"} and name.startswith("readme"):
                continue  # already inlined above
            content = read_text_file(str(clone_path / path))
            if not content or not content.strip():
                continue
            snippet = content[:_MAX_FILE_CHARS]
            budget -= len(snippet)
            if budget <= 0:
                parts.append("_… remaining files omitted (size budget reached)._")
                break
            lang = _FENCE_LANG.get(suffix, "")
            parts += [f"### `{path}`", "", f"```{lang}", snippet, "```", ""]

        return "\n".join(parts)

    def _read_readme(self, clone_path: Path, files: list[str]) -> str | None:
        for path in files:
            if "/" not in path and Path(path).name.lower().startswith("readme"):
                return read_text_file(str(clone_path / path))
        return None
