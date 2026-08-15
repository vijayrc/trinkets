"""File discovery and cheap per-file measurement.

The walker reads every candidate file exactly once and hands the decoded text to
the probes, so an eight-part report still costs a single pass over the tree.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from trinkets.repostats import languages
from trinkets.repostats.gitio import GitError, GitRunner

# Directories that are never the repo's own source.
EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn", ".idea", ".vscode", ".vs",
    "node_modules", "bower_components", "vendor", "third_party", "thirdparty",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox",
    "venv", ".venv", "env", ".env.d", "virtualenv", "site-packages",
    "dist", "build", "out", "target", "bin", "obj", ".next", ".nuxt", ".svelte-kit",
    "coverage", "htmlcov", ".gradle", ".terraform", "Pods", "DerivedData",
    ".eggs", ".cache", ".parcel-cache", ".turbo", "cdk.out",
})

# Generated or lock artefacts: real files, but not authored code.
GENERATED_FILENAMES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock",
    "composer.lock", "Cargo.lock", "go.sum", "gemfile.lock", "uv.lock", "pdm.lock",
})

GENERATED_SUFFIXES: tuple[str, ...] = (
    ".min.js", ".min.css", ".bundle.js", ".map", "_pb2.py", "_pb2_grpc.py",
    ".pb.go", ".g.dart", ".generated.ts", ".designer.cs",
)

MAX_FILE_BYTES = 2_000_000        # skip anything bigger; almost certainly data
BINARY_SNIFF_BYTES = 8192


@dataclass
class SourceFile:
    """One analysed file, read once and shared across all probes."""

    relpath: str
    abspath: Path
    language: str | None
    size_bytes: int
    text: str | None = None            # None when binary or unreadable
    lines: list[str] = field(default_factory=list)
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0

    @property
    def name(self) -> str:
        return self.abspath.name

    @property
    def posix_relpath(self) -> str:
        return self.relpath.replace(os.sep, "/")

    @property
    def is_code(self) -> bool:
        return self.language is not None and languages.is_code(self.language)


def _is_probably_binary(chunk: bytes) -> bool:
    if b"\0" in chunk:
        return True
    if not chunk:
        return False
    # Heuristic: lots of bytes outside printable ASCII + common control chars.
    text_chars = bytes(range(32, 127)) + b"\n\r\t\f\b"
    non_text = sum(1 for byte in chunk if byte not in text_chars)
    return non_text / len(chunk) > 0.30


def _count_lines(text_lines: list[str], language: str | None) -> tuple[int, int, int]:
    """Return (code, comment, blank) counts for already-split lines."""
    if not language:
        non_blank = sum(1 for line in text_lines if line.strip())
        return non_blank, 0, len(text_lines) - non_blank

    line_prefixes, block = languages.COMMENT_SYNTAX.get(language, ((), None))
    code = comment = blank = 0
    in_block = False
    block_start, block_end = block if block else ("", "")

    for raw in text_lines:
        stripped = raw.strip()
        if not stripped:
            blank += 1
            continue

        if in_block:
            comment += 1
            if block_end and block_end in stripped:
                in_block = False
            continue

        if block_start and stripped.startswith(block_start):
            comment += 1
            # Single-line block comment (e.g. /* note */ or a one-line docstring).
            rest = stripped[len(block_start):]
            if not (block_end and block_end in rest):
                in_block = True
            continue

        if line_prefixes and any(stripped.startswith(prefix) for prefix in line_prefixes):
            comment += 1
            continue

        code += 1

    return code, comment, blank


def _is_generated(relpath: str, name: str) -> bool:
    if name.lower() in GENERATED_FILENAMES:
        return True
    return any(name.endswith(suffix) for suffix in GENERATED_SUFFIXES)


def _iter_candidate_paths(repo_path: Path, git: GitRunner | None) -> Iterator[str]:
    """Yield repo-relative paths, preferring git's index so .gitignore is honoured."""
    if git is not None:
        try:
            tracked = git.tracked_files()
            if tracked:
                yield from tracked
                return
        except GitError:
            pass

    for root, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".git")]
        for filename in filenames:
            full = Path(root) / filename
            try:
                yield str(full.relative_to(repo_path))
            except ValueError:
                continue


def walk(
    repo_path: Path,
    git: GitRunner | None = None,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> tuple[list[SourceFile], list[str], int]:
    """Read the repository once.

    Returns (files, warnings, skipped_count). Files with unreadable or binary
    content are still returned (with ``text=None``) so they count toward totals.
    """
    files: list[SourceFile] = []
    warnings: list[str] = []
    skipped = 0

    for relpath in _iter_candidate_paths(repo_path, git):
        parts = Path(relpath).parts
        if any(part in EXCLUDED_DIRS for part in parts):
            skipped += 1
            continue

        abspath = repo_path / relpath
        name = abspath.name
        if _is_generated(relpath, name):
            skipped += 1
            continue

        try:
            if not abspath.is_file() or abspath.is_symlink():
                skipped += 1
                continue
            size = abspath.stat().st_size
        except OSError:
            skipped += 1
            continue

        if size > max_file_bytes:
            skipped += 1
            continue

        first_line: str | None = None
        text: str | None = None
        try:
            raw = abspath.read_bytes()
            if _is_probably_binary(raw[:BINARY_SNIFF_BYTES]):
                skipped += 1
                continue
            text = raw.decode("utf-8", errors="replace")
            first_line = text.split("\n", 1)[0] if text else None
        except OSError as exc:
            warnings.append(f"Could not read {relpath}: {exc}")
            skipped += 1
            continue

        language = languages.classify(name, first_line)
        line_list = text.splitlines() if text else []
        code, comment, blank = _count_lines(line_list, language)

        files.append(
            SourceFile(
                relpath=relpath,
                abspath=abspath,
                language=language,
                size_bytes=size,
                text=text,
                lines=line_list,
                total_lines=len(line_list),
                code_lines=code,
                comment_lines=comment,
                blank_lines=blank,
            )
        )

    return files, warnings, skipped
