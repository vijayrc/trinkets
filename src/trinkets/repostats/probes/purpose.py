"""Probe 3: inferred purpose of the repository.

This is the most speculative section in the report.  It reads what the project
says about itself (README, package metadata) and corroborates that against what
the code actually contains, then labels the result with a confidence level.
It does not attempt to summarise business logic it cannot see.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter

from trinkets.repostats.models import ApiEndpoint, BuildInfo, Confidence, Evidence, PurposeInfo
from trinkets.repostats.walker import SourceFile

BADGE_LINE = re.compile(r"^\s*(?:\[!\[|!\[|<img|<p\s|<div\s|<h\d|<a\s|=+\s*$|-+\s*$)")
MD_DECORATION = re.compile(r"[`*_>#]|\[([^\]]*)\]\([^)]*\)")

STOPWORDS = frozenset({
    "src", "lib", "app", "apps", "main", "core", "common", "utils", "util", "test", "tests",
    "docs", "doc", "internal", "pkg", "cmd", "api", "web", "config", "scripts", "build",
    "index", "types", "helpers", "shared", "base", "public", "static", "assets", "dist",
    "the", "and", "for", "with", "from", "this", "that", "new", "old", "temp", "tmp",
})

CLI_SIGNALS = (
    "argparse", "click", "typer", "docopt", "commander", "yargs", "oclif",
    "cobra", "clap", "picocli", "thor",
)

KIND_ORDER = (
    "HTTP service / web API",
    "web frontend",
    "CLI tool",
    "library / SDK",
    "data pipeline / analytics",
    "machine learning",
    "infrastructure as code",
    "mobile app",
    "documentation site",
    "monorepo of services",
)


def _clean_markdown(line: str) -> str:
    cleaned = MD_DECORATION.sub(lambda m: m.group(1) or "", line).strip()
    return re.sub(r"\s+", " ", cleaned)


def _readme_excerpt(readme: SourceFile | None) -> tuple[str | None, str | None]:
    """Return (title, first substantive paragraph)."""
    if readme is None or not readme.text:
        return None, None

    title: str | None = None
    paragraph: list[str] = []

    for raw in readme.lines[:120]:
        line = raw.strip()
        if not line:
            if paragraph:
                break
            continue
        if line.startswith("#") and title is None:
            title = _clean_markdown(line.lstrip("#").strip()) or None
            continue
        if BADGE_LINE.match(line):
            continue
        if line.startswith(("---", "===", "```", "|", ":--")):
            if paragraph:
                break
            continue
        cleaned = _clean_markdown(line)
        if cleaned:
            paragraph.append(cleaned)
        if sum(len(part) for part in paragraph) > 400:
            break

    text = " ".join(paragraph).strip()
    if len(text) > 500:
        text = text[:497].rsplit(" ", 1)[0] + "..."
    return title, text or None


def _declared_metadata(files: list[SourceFile]) -> tuple[str | None, str | None]:
    """Return (project name, description) from package metadata."""
    by_name = {source.posix_relpath: source for source in files}

    pyproject = by_name.get("pyproject.toml")
    if pyproject and pyproject.text:
        try:
            data = tomllib.loads(pyproject.text)
            project = data.get("project") or {}
            poetry = (data.get("tool") or {}).get("poetry") or {}
            name = project.get("name") or poetry.get("name")
            description = project.get("description") or poetry.get("description")
            if name or description:
                return name, description
        except (tomllib.TOMLDecodeError, ValueError):
            pass

    package_json = by_name.get("package.json")
    if package_json and package_json.text:
        try:
            data = json.loads(package_json.text)
            if isinstance(data, dict):
                return data.get("name"), data.get("description")
        except (json.JSONDecodeError, ValueError):
            pass

    pom = by_name.get("pom.xml")
    if pom and pom.text:
        name = re.search(r"<artifactId>\s*([^<]+?)\s*</artifactId>", pom.text)
        description = re.search(r"<description>\s*([^<]+?)\s*</description>", pom.text, re.DOTALL)
        if name or description:
            return (
                name.group(1) if name else None,
                re.sub(r"\s+", " ", description.group(1)).strip() if description else None,
            )

    cargo = by_name.get("Cargo.toml")
    if cargo and cargo.text:
        try:
            data = tomllib.loads(cargo.text)
            package = data.get("package") or {}
            return package.get("name"), package.get("description")
        except (tomllib.TOMLDecodeError, ValueError):
            pass

    return None, None


def _domain_terms(files: list[SourceFile], limit: int = 12) -> list[str]:
    """Recurring identifiers in paths — a rough proxy for the problem domain."""
    counter: Counter[str] = Counter()
    for source in files:
        if not source.is_code:
            continue
        parts = source.posix_relpath.replace("\\", "/").split("/")
        stem = parts[-1].rsplit(".", 1)[0]
        for token in [*parts[:-1], stem]:
            for word in re.split(r"[-_.\s]+|(?<=[a-z])(?=[A-Z])", token):
                word = word.strip().lower()
                if len(word) < 4 or word in STOPWORDS or word.isdigit():
                    continue
                counter[word] += 1
    return [word for word, count in counter.most_common(limit) if count >= 2]


def analyse(
    files: list[SourceFile],
    build: BuildInfo,
    endpoints: list[ApiEndpoint],
    frameworks: list[str],
    languages_ranked: list[str],
) -> PurposeInfo:
    info = PurposeInfo()
    evidence: list[Evidence] = []

    readme = next(
        (source for source in files
         if source.name.lower().startswith("readme") and source.posix_relpath.count("/") == 0),
        None,
    )
    title, excerpt = _readme_excerpt(readme)
    info.readme_excerpt = excerpt
    if readme is not None:
        evidence.append(Evidence("Read project README", readme.posix_relpath))

    name, description = _declared_metadata(files)
    info.project_name = name or title
    info.declared_description = description
    if description:
        evidence.append(Evidence("Package metadata declares a description"))

    info.frameworks = frameworks

    # --- what kind of thing is this? ------------------------------------
    kinds: set[str] = set()
    all_text_names = {source.posix_relpath.lower() for source in files}

    if endpoints:
        kinds.add("HTTP service / web API")
        evidence.append(Evidence(f"Found {len(endpoints)} HTTP route declarations"))

    web_frontend = {"React", "Vue", "Angular", "Svelte", "Next.js", "Nuxt"}
    if any(framework in web_frontend for framework in frameworks):
        kinds.add("web frontend")
    if any(name.endswith((".tsx", ".jsx", ".vue", ".svelte")) for name in all_text_names):
        kinds.add("web frontend")

    if build.tools and any("script" in tool.lower() for tool in build.tools):
        pass
    has_console_script = False
    for source in files:
        if source.name.lower() == "pyproject.toml" and source.text:
            if "[project.scripts]" in source.text or "console_scripts" in source.text:
                has_console_script = True
        if source.name.lower() == "package.json" and source.text and '"bin"' in source.text:
            has_console_script = True
    if has_console_script:
        kinds.add("CLI tool")
        evidence.append(Evidence("Package metadata declares an executable entry point"))

    code_text_sample = " ".join(
        source.text[:4000] for source in files
        if source.text and source.is_code and source.posix_relpath.count("/") <= 3
    ).lower()
    for signal in CLI_SIGNALS:
        if signal in code_text_sample:
            kinds.add("CLI tool")
            evidence.append(Evidence(f"CLI framework referenced in source: {signal}"))
            break

    if any(name.endswith(".tf") for name in all_text_names):
        kinds.add("infrastructure as code")
    if any(name.endswith(".ipynb") for name in all_text_names):
        kinds.add("data pipeline / analytics")
    if any(framework in {"pandas", "NumPy", "Apache Spark", "Dask", "Polars"}
           for framework in frameworks):
        kinds.add("data pipeline / analytics")
    if any(framework in {"PyTorch", "TensorFlow", "scikit-learn", "Hugging Face Transformers",
                         "LangChain", "OpenAI API", "Anthropic API"} for framework in frameworks):
        kinds.add("machine learning")
    if any(name.endswith((".swift", ".kt")) and "android" in name for name in all_text_names):
        kinds.add("mobile app")
    if len(build.workspaces) >= 3:
        kinds.add("monorepo of services")

    is_publishable = bool(
        {"pyproject.toml", "setup.py", "package.json", "Cargo.toml"} & {
            source.posix_relpath for source in files
        }
    )
    if is_publishable and not kinds:
        kinds.add("library / SDK")

    info.detected_kinds = [kind for kind in KIND_ORDER if kind in kinds]
    info.domain_terms = _domain_terms(files)

    # --- assemble a summary ---------------------------------------------
    subject = info.project_name or "This repository"
    primary_language = languages_ranked[0] if languages_ranked else "an unidentified language"

    if description:
        summary = f"{subject} — {description.rstrip('.')}."
        info.confidence = Confidence.HIGH
    elif excerpt:
        summary = f"{subject} — {excerpt.rstrip('.')}."
        info.confidence = Confidence.MEDIUM
    else:
        summary = f"{subject} is a {primary_language} project."
        info.confidence = Confidence.LOW

    detail_parts: list[str] = []
    if info.detected_kinds:
        detail_parts.append("It looks like a " + " and ".join(info.detected_kinds).lower())
    if frameworks:
        detail_parts.append(f"built with {', '.join(frameworks[:5])}")
    if primary_language and not description:
        detail_parts.append(f"written mainly in {primary_language}")
    if detail_parts:
        summary += " " + ", ".join(detail_parts) + "."

    info.summary = summary
    info.evidence = evidence
    return info
