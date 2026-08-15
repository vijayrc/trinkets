"""Orchestrator: walks the repository once, then runs every probe over the result."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from trinkets import __version__
from trinkets.repostats import walker
from trinkets.repostats.gitio import GitError, GitRunner
from trinkets.repostats.models import RepoReport
from trinkets.repostats.probes import build as build_probe
from trinkets.repostats.probes import codestats as code_probe
from trinkets.repostats.probes import contributors as contributor_probe
from trinkets.repostats.probes import dependencies as dependency_probe
from trinkets.repostats.probes import flow as flow_probe
from trinkets.repostats.probes import purpose as purpose_probe
from trinkets.repostats.probes import testing as testing_probe

# Dependency categories whose entries read as "frameworks" in the summary.
FRAMEWORK_CATEGORIES = ("web framework", "rpc", "data", "task queue")


def analyse_repository(
    repo_path: Path,
    max_commits: int | None = None,
    run_coverage: bool = False,
    max_file_bytes: int = walker.MAX_FILE_BYTES,
) -> RepoReport:
    repo_path = repo_path.resolve()
    if not repo_path.is_dir():
        raise NotADirectoryError(f"{repo_path} is not a directory")

    git: GitRunner | None = GitRunner(repo_path)
    is_git_repo = git.is_repo()
    if not is_git_repo:
        git = None

    report = RepoReport(
        path=str(repo_path),
        name=repo_path.name,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        analyser_version=__version__,
        is_git_repo=is_git_repo,
    )

    if git is not None:
        try:
            report.head_commit = git.head_commit()
            report.branch = git.branch()
            report.remote = git.remote_url()
        except GitError as exc:
            report.warnings.append(f"git metadata unavailable: {exc}")
    else:
        report.warnings.append(
            "Not a git repository — contributor and history sections will be empty, and "
            "file discovery falls back to a filesystem walk that cannot honour .gitignore."
        )

    # --- single pass over the tree ---------------------------------------
    files, warnings, skipped = walker.walk(repo_path, git, max_file_bytes=max_file_bytes)
    report.warnings.extend(warnings)

    if not files:
        report.warnings.append("No analysable files found.")
        return report

    # --- probes ----------------------------------------------------------
    report.languages, report.code = code_probe.analyse(files, skipped)
    report.build = build_probe.analyse(files)
    report.dependencies = dependency_probe.analyse(files)
    report.contributors = contributor_probe.analyse(git, max_commits=max_commits)

    frameworks: list[str] = []
    for category in FRAMEWORK_CATEGORIES:
        frameworks.extend(report.dependencies.by_category.get(category, []))

    ranked_languages = [entry.language for entry in report.languages if entry.is_code]

    report.purpose = purpose_probe.analyse(
        files,
        build=report.build,
        endpoints=report.code.endpoints,
        frameworks=frameworks,
        languages_ranked=ranked_languages,
    )

    report.flow = flow_probe.analyse(
        files,
        endpoints=report.code.endpoints,
        dependencies=report.dependencies,
        frameworks=frameworks,
    )

    declared_test_tools = report.dependencies.by_category.get("testing", [])
    report.testing = testing_probe.analyse(
        files,
        repo_path=repo_path,
        declared_test_tools=declared_test_tools,
        run_coverage=run_coverage,
    )

    if report.contributors.shallow_or_partial:
        report.warnings.append(
            "This is a shallow clone; contributor totals and the first-commit date reflect only "
            "the fetched history."
        )

    return report
