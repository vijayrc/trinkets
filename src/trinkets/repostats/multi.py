"""Discover every git repository under a folder and publish a consolidated HTML report."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from trinkets.repostats.analyzer import analyse_repository
from trinkets.repostats.gitio import GitError
from trinkets.repostats.models import RepoReport
from trinkets.repostats.render.html import render_index, render_repo_report, render_source_file
from trinkets.repostats.walker import EXCLUDED_DIRS, MAX_FILE_BYTES

_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def discover_repos(root: Path, max_depth: int = 6) -> list[Path]:
    """Find every git working tree under `root`, without descending into one once found."""
    root = root.resolve()
    if (root / ".git").exists():
        return [root]

    found: list[Path] = []

    def _walk(directory: Path, depth: int) -> None:
        if (directory / ".git").exists():
            found.append(directory)
            return
        if depth >= max_depth:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for entry in children:
            try:
                if entry.is_symlink() or not entry.is_dir():
                    continue
            except OSError:
                continue
            if entry.name in EXCLUDED_DIRS or entry.name.startswith("."):
                continue
            _walk(entry, depth + 1)

    _walk(root, 0)
    return found


def _slugify(name: str, used: set[str]) -> str:
    slug = _SLUG_RE.sub("-", name).strip("-") or "repo"
    candidate = slug
    n = 2
    while candidate in used:
        candidate = f"{slug}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def _referenced_paths(report: RepoReport) -> set[str]:
    paths: set[str] = set()

    def add(value: str | None) -> None:
        if value:
            paths.add(value)

    for path, _ in report.code.largest_files:
        add(path)
    for endpoint in report.code.endpoints:
        add(endpoint.path)
    for manifest in report.build.manifests:
        add(manifest)
    for dep in report.dependencies.declared:
        add(dep.source)
    for dep in report.dependencies.infrastructure:
        add(dep.source)
    for evidence in report.purpose.evidence:
        add(evidence.path)
    for node in report.flow.nodes:
        for evidence in node.evidence:
            add(evidence.path)
    for evidence in report.testing.evidence:
        add(evidence.path)
    return paths


@dataclass
class ScanEntry:
    display_path: str
    slug: str
    report: RepoReport | None
    error: str | None = None


def _write_source_pages(
    repo_path: Path, repo_dir: Path, report: RepoReport, max_file_bytes: int
) -> set[str]:
    generated: set[str] = set()
    for relpath in sorted(_referenced_paths(report)):
        source = repo_path / relpath
        try:
            if not source.is_file() or source.stat().st_size > max_file_bytes:
                continue
            text = source.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue

        dest = repo_dir / "files" / relpath
        dest_html = dest.with_name(dest.name + ".html")
        dest_html.parent.mkdir(parents=True, exist_ok=True)

        depth = len(Path(relpath).parts)
        report_href = "../" * depth + "report.html"
        index_href = "../" * depth + "../index.html"
        dest_html.write_text(
            render_source_file(
                relpath, text, repo_name=repo_path.name,
                report_href=report_href, index_href=index_href,
            ),
            encoding="utf-8",
        )
        generated.add(relpath)
    return generated


def scan(
    root: Path,
    output_dir: Path,
    *,
    max_depth: int = 6,
    max_commits: int | None = None,
    max_file_bytes: int = MAX_FILE_BYTES,
    run_coverage: bool = False,
    on_progress: Callable[[str], None] = lambda _msg: None,
) -> tuple[list[ScanEntry], Path]:
    """Analyse every repo under `root` and write a consolidated HTML report to `output_dir`."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    repo_paths = discover_repos(root, max_depth=max_depth)

    output_dir.mkdir(parents=True, exist_ok=True)

    entries: list[ScanEntry] = []
    used_slugs: set[str] = set()

    for repo_path in repo_paths:
        try:
            display_path = str(repo_path.relative_to(root))
        except ValueError:
            display_path = str(repo_path)
        if display_path == ".":
            display_path = repo_path.name

        slug = _slugify(repo_path.name, used_slugs)
        on_progress(display_path)

        try:
            report = analyse_repository(
                repo_path, max_commits=max_commits,
                run_coverage=run_coverage, max_file_bytes=max_file_bytes,
            )
        except (GitError, NotADirectoryError, OSError) as exc:
            entries.append(
                ScanEntry(display_path=display_path, slug=slug, report=None, error=str(exc))
            )
            continue

        repo_dir = output_dir / slug
        generated_files = _write_source_pages(repo_path, repo_dir, report, max_file_bytes)

        def file_href(relpath: str, _generated: set[str] = generated_files) -> str | None:
            if relpath not in _generated:
                return None
            return "files/" + "/".join(quote(part) for part in Path(relpath).parts) + ".html"

        (repo_dir / "report.html").write_text(
            render_repo_report(report, file_href=file_href), encoding="utf-8"
        )
        entries.append(ScanEntry(display_path=display_path, slug=slug, report=report, error=None))

    _write_index(root, output_dir, entries)
    return entries, output_dir


def _write_index(root: Path, output_dir: Path, entries: list[ScanEntry]) -> None:
    from datetime import datetime, timezone

    rows = []
    errors: list[tuple[str, str]] = []
    for entry in entries:
        if entry.report is None:
            errors.append((entry.display_path, entry.error or "unknown error"))
            continue
        report = entry.report
        code_languages = [lang for lang in report.languages if lang.is_code]
        primary = code_languages[0].language if code_languages else None
        rows.append(
            {
                "name": report.name,
                "display_path": entry.display_path,
                "report_href": f"{quote(entry.slug)}/report.html",
                "language": primary,
                "code_lines": report.code.code_lines,
                "files": report.code.analysed_files,
                "contributors": report.contributors.total_authors,
                "commits": report.contributors.total_commits,
                "bus_factor": report.contributors.bus_factor,
                "warnings": len(report.warnings),
            }
        )

    index_html = render_index(
        root.name, datetime.now(timezone.utc).isoformat(timespec="seconds"), rows, errors
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
