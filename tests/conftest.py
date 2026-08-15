from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def make_repo(tmp_path: Path):
    """Build a throwaway git repository from a {relative path: contents} mapping."""

    def _make(files: dict[str, str], commit: bool = True, name: str = "sample") -> Path:
        repo = tmp_path / name
        repo.mkdir(parents=True, exist_ok=True)
        for relpath, contents in files.items():
            target = repo / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")

        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "dev@example.com")
        _git(repo, "config", "user.name", "Test Dev")
        if commit:
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "Initial commit")
        return repo

    return _make
