"""Thin wrapper around the git CLI.

Shelling out to git keeps the tool dependency-free and matches whatever git
already understands about the repo (worktrees, submodules, mailmap, ...).
Every call is read-only.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT_SECONDS = 60


class GitError(RuntimeError):
    pass


@dataclass
class GitRunner:
    repo_path: Path
    timeout: int = GIT_TIMEOUT_SECONDS

    def run(self, *args: str, check: bool = True) -> str:
        """Run a git command in the repo and return stdout."""
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.repo_path), *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                errors="replace",
            )
        except FileNotFoundError as exc:  # git not installed
            raise GitError("git executable not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args)} timed out after {self.timeout}s") from exc

        if completed.returncode != 0:
            if check:
                stderr = completed.stderr.strip() or "(no stderr)"
                raise GitError(f"git {' '.join(args)} failed: {stderr}")
            return ""
        return completed.stdout

    def is_repo(self) -> bool:
        try:
            return self.run("rev-parse", "--is-inside-work-tree", check=False).strip() == "true"
        except GitError:
            return False

    def head_commit(self) -> str | None:
        return self.run("rev-parse", "HEAD", check=False).strip() or None

    def branch(self) -> str | None:
        return self.run("rev-parse", "--abbrev-ref", "HEAD", check=False).strip() or None

    def remote_url(self) -> str | None:
        url = self.run("config", "--get", "remote.origin.url", check=False).strip()
        return url or None

    def is_shallow(self) -> bool:
        return self.run("rev-parse", "--is-shallow-repository", check=False).strip() == "true"

    def tracked_files(self) -> list[str]:
        """Files git would consider part of the working tree.

        Includes untracked-but-not-ignored files, so a repo with uncommitted work
        in progress still reports on everything the developer can see, while
        .gitignore is still honoured via ``--exclude-standard``.
        """
        output = self.run(
            "ls-files", "-z", "--cached", "--others", "--exclude-standard", check=False
        )
        # --cached and --others can both list the same path; de-duplicate, keep order.
        seen: set[str] = set()
        results: list[str] = []
        for item in output.split("\0"):
            if item and item not in seen:
                seen.add(item)
                results.append(item)
        return results

    def commit_count(self) -> int:
        raw = self.run("rev-list", "--count", "HEAD", check=False).strip()
        return int(raw) if raw.isdigit() else 0

    def log_with_numstat(self, max_commits: int | None = None) -> str:
        """One record per commit: metadata line followed by numstat rows.

        ``--no-merges`` keeps merge commits from double-counting line churn that
        was already attributed to the original authoring commits.
        """
        args = [
            "log",
            "--no-merges",
            "--numstat",
            "--date=short",
            "--format=\x01%H\x02%an\x02%ae\x02%ad\x02%aI",
        ]
        if max_commits:
            args.append(f"--max-count={max_commits}")
        return self.run(*args, check=False)
