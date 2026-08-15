"""Probe 8: test tooling and coverage.

Coverage is *read* from reports the repo already contains — this probe never
executes the analysed repository's test suite, since that would mean running
arbitrary third-party code.  ``repostats --run-coverage`` opts into that
explicitly and is documented as such.
"""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from trinkets.repostats.models import Confidence, Evidence, TestingInfo
from trinkets.repostats.walker import SourceFile

TEST_PATH_MARKERS = ("test", "tests", "spec", "specs", "__tests__", "testing", "e2e", "it")

TEST_FILENAME = re.compile(
    r"(^test_.*|.*_test\.[\w]+$|.*\.test\.[\w]+$|.*\.spec\.[\w]+$|.*Test\.\w+$|.*Tests\.\w+$"
    r"|.*Spec\.\w+$|^conftest\.py$)"
)

# framework -> (config filenames, import/usage fragments)
FRAMEWORK_SIGNALS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "pytest": (("pytest.ini", "conftest.py", "tox.ini"), ("import pytest", "from pytest")),
    "unittest": ((), ("import unittest", "from unittest")),
    "Hypothesis": ((), ("from hypothesis", "import hypothesis")),
    # "describe(" is deliberately not a Jest signal — Vitest, Mocha and
    # Playwright all use it, so it would misattribute half the JS ecosystem.
    "Jest": (("jest.config.js", "jest.config.ts", "jest.config.mjs"),
             ("from '@jest", "jest.mock(", "jest.fn(")),
    "Vitest": (("vitest.config.ts", "vitest.config.js"), ("from 'vitest'", "from \"vitest\"")),
    "Mocha": ((".mocharc.json", ".mocharc.yml"), ("require('mocha')",)),
    "Cypress": (("cypress.config.js", "cypress.config.ts", "cypress.json"), ("cy.visit(",)),
    "Playwright": (("playwright.config.ts", "playwright.config.js"),
                   ("@playwright/test", "from 'playwright'")),
    "JUnit": ((), ("org.junit", "@Test")),
    "Mockito": ((), ("org.mockito",)),
    "Testcontainers": ((), ("org.testcontainers", "testcontainers")),
    "RSpec": ((".rspec",), ("require 'rspec'", "RSpec.describe")),
    "Go testing": ((), ("testing.T", "testing.B")),
    "testify": ((), ("stretchr/testify",)),
    "Rust test harness": ((), ("#[test]", "#[cfg(test)]")),
    "PHPUnit": (("phpunit.xml", "phpunit.xml.dist"), ("PHPUnit\\Framework",)),
}

COVERAGE_TOOL_FILES: dict[str, str] = {
    ".coveragerc": "coverage.py",
    "codecov.yml": "Codecov",
    ".codecov.yml": "Codecov",
    "jacoco.xml": "JaCoCo",
    ".nycrc": "nyc",
    ".nycrc.json": "nyc",
}


def _is_test_file(source: SourceFile) -> bool:
    parts = [part.lower() for part in Path(source.posix_relpath).parts[:-1]]
    if any(part in TEST_PATH_MARKERS for part in parts):
        return True
    return bool(TEST_FILENAME.match(source.name))


def _parse_cobertura(text: str) -> float | None:
    """coverage.xml from coverage.py / Cobertura: line-rate on the root element."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    rate = root.get("line-rate")
    if rate:
        try:
            return round(float(rate) * 100, 2)
        except ValueError:
            return None
    # JaCoCo: <counter type="LINE" missed="x" covered="y"/> at report level
    for counter in root.findall("counter"):
        if counter.get("type") == "LINE":
            missed = int(counter.get("missed", 0))
            covered = int(counter.get("covered", 0))
            total = missed + covered
            if total:
                return round(covered / total * 100, 2)
    return None


def _parse_coverage_json(text: str) -> float | None:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    totals = data.get("totals")
    if isinstance(totals, dict):
        percent = totals.get("percent_covered")
        if isinstance(percent, int | float):
            return round(float(percent), 2)
    # Istanbul summary format
    total = data.get("total")
    if isinstance(total, dict) and isinstance(total.get("lines"), dict):
        percent = total["lines"].get("pct")
        if isinstance(percent, int | float):
            return round(float(percent), 2)
    return None


def _parse_lcov(text: str) -> float | None:
    found = hit = 0
    for line in text.splitlines():
        if line.startswith("LF:"):
            found += int(line[3:] or 0)
        elif line.startswith("LH:"):
            hit += int(line[3:] or 0)
    return round(hit / found * 100, 2) if found else None


COVERAGE_PARSERS: tuple[tuple[str, str], ...] = (
    ("coverage.xml", "cobertura"),
    ("cobertura.xml", "cobertura"),
    ("jacoco.xml", "cobertura"),
    ("jacocotestreport.xml", "cobertura"),
    ("coverage.json", "json"),
    ("coverage-summary.json", "json"),
    ("coverage-final.json", "json"),
    ("lcov.info", "lcov"),
)


def _find_coverage(files: list[SourceFile], repo_path: Path) -> tuple[float | None, str | None]:
    # Reports are often gitignored, so check the filesystem too.
    candidates: list[tuple[Path, str, str]] = []
    for source in files:
        for filename, kind in COVERAGE_PARSERS:
            if source.name.lower() == filename:
                candidates.append((source.abspath, kind, source.posix_relpath))

    for filename, kind in COVERAGE_PARSERS:
        for location in (repo_path / filename, repo_path / "coverage" / filename,
                         repo_path / "htmlcov" / filename, repo_path / "build" / "reports" / filename):
            if location.is_file():
                candidates.append((location, kind, str(location.relative_to(repo_path))))

    for path, kind, relpath in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if kind == "cobertura":
            percent = _parse_cobertura(text)
        elif kind == "json":
            percent = _parse_coverage_json(text)
        else:
            percent = _parse_lcov(text)
        if percent is not None:
            return percent, relpath
    return None, None


def _run_coverage(repo_path: Path, timeout: int = 600) -> tuple[float | None, str | None, str]:
    """Opt-in: actually execute the repo's pytest suite under coverage."""
    command = ["python", "-m", "pytest", "--cov", "--cov-report=json:.repostats-coverage.json", "-q"]
    try:
        subprocess.run(
            command, cwd=repo_path, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, None, f"Coverage run failed: {exc}"

    report = repo_path / ".repostats-coverage.json"
    if not report.is_file():
        return None, None, "Coverage run produced no JSON report (is pytest-cov installed?)."
    try:
        percent = _parse_coverage_json(report.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        return None, None, f"Could not read coverage report: {exc}"
    finally:
        report.unlink(missing_ok=True)
    return percent, "pytest --cov (executed by repostats)", ""


def analyse(
    files: list[SourceFile],
    repo_path: Path,
    declared_test_tools: list[str] | None = None,
    run_coverage: bool = False,
) -> TestingInfo:
    info = TestingInfo()
    frameworks: set[str] = set(declared_test_tools or [])
    coverage_tools: set[str] = set()

    test_files: list[SourceFile] = []
    source_files: list[SourceFile] = []

    for source in files:
        if not source.is_code:
            if source.name.lower() in COVERAGE_TOOL_FILES:
                coverage_tools.add(COVERAGE_TOOL_FILES[source.name.lower()])
            continue
        if _is_test_file(source):
            test_files.append(source)
        else:
            source_files.append(source)

    # Framework detection from config filenames and in-file usage.
    filenames = {source.name.lower() for source in files}
    for framework, (config_files, fragments) in FRAMEWORK_SIGNALS.items():
        if any(config.lower() in filenames for config in config_files):
            frameworks.add(framework)
            continue
        if not fragments:
            continue
        for source in test_files:
            if source.text and any(fragment in source.text for fragment in fragments):
                frameworks.add(framework)
                break

    for source in files:
        name = source.name.lower()
        if name in COVERAGE_TOOL_FILES:
            coverage_tools.add(COVERAGE_TOOL_FILES[name])
        if name == "pyproject.toml" and source.text and "[tool.coverage" in source.text:
            coverage_tools.add("coverage.py")
        if name == "package.json" and source.text:
            if '"nyc"' in source.text:
                coverage_tools.add("nyc")
            if "c8" in source.text:
                coverage_tools.add("c8")

    info.frameworks = sorted(frameworks)
    info.coverage_tools_configured = sorted(coverage_tools)
    info.test_files = len(test_files)
    info.source_files = len(source_files)
    info.test_lines = sum(source.code_lines for source in test_files)
    info.test_to_source_ratio = (
        round(len(test_files) / len(source_files), 3) if source_files else 0.0
    )

    test_function = re.compile(
        r"^\s*(?:async\s+)?def\s+test_\w+|^\s*(?:it|test|describe)\s*\(|@Test\b|^\s*func\s+Test\w+"
        r"|#\[test\]",
        re.MULTILINE,
    )
    info.test_functions = sum(
        len(test_function.findall(source.text)) for source in test_files if source.text
    )

    for source in test_files[:5]:
        info.evidence.append(Evidence("Test file", source.posix_relpath))

    if run_coverage:
        percent, label, error = _run_coverage(repo_path)
        if percent is not None:
            info.coverage_percent = percent
            info.coverage_source = label
        elif error:
            info.note = error

    if info.coverage_percent is None:
        percent, source_label = _find_coverage(files, repo_path)
        info.coverage_percent = percent
        info.coverage_source = source_label

    if info.coverage_percent is None and not info.note:
        if coverage_tools:
            info.note = (
                f"Coverage tooling is configured ({', '.join(sorted(coverage_tools))}) but no "
                "coverage report was found in the tree. Run the suite, or pass --run-coverage "
                "to let repostats execute pytest itself."
            )
        else:
            info.note = (
                "No coverage report or coverage tooling found. Coverage is not measured here "
                "because doing so means executing the repository's test suite."
            )

    return info


TESTING_CONFIDENCE = Confidence.MEDIUM
