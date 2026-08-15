"""Probe 2: build tooling and project model."""

from __future__ import annotations

import json
import re
import tomllib

from trinkets.repostats.models import BuildInfo, Evidence
from trinkets.repostats.walker import SourceFile

# marker filename -> (build tool, package manager or None)
MARKERS: dict[str, tuple[str, str | None]] = {
    "pyproject.toml": ("Python packaging", None),
    "setup.py": ("setuptools", "pip"),
    "setup.cfg": ("setuptools", "pip"),
    "requirements.txt": ("pip", "pip"),
    "pipfile": ("Pipenv", "pipenv"),
    "poetry.lock": ("Poetry", "poetry"),
    "uv.lock": ("uv", "uv"),
    "pdm.lock": ("PDM", "pdm"),
    "environment.yml": ("Conda", "conda"),
    "package.json": ("npm-compatible", "npm"),
    "pom.xml": ("Maven", "maven"),
    "build.gradle": ("Gradle", "gradle"),
    "build.gradle.kts": ("Gradle (Kotlin DSL)", "gradle"),
    "settings.gradle": ("Gradle", "gradle"),
    "settings.gradle.kts": ("Gradle (Kotlin DSL)", "gradle"),
    "build.sbt": ("sbt", "sbt"),
    "cargo.toml": ("Cargo", "cargo"),
    "go.mod": ("Go modules", "go"),
    "gemfile": ("Bundler", "bundler"),
    "composer.json": ("Composer", "composer"),
    "mix.exs": ("Mix", "hex"),
    "makefile": ("Make", None),
    "cmakelists.txt": ("CMake", None),
    "meson.build": ("Meson", None),
    "build": ("Bazel", "bazel"),
    "build.bazel": ("Bazel", "bazel"),
    "workspace": ("Bazel", "bazel"),
    "module.bazel": ("Bazel", "bazel"),
    "justfile": ("just", None),
    "taskfile.yml": ("Task", None),
    "dockerfile": ("Docker", None),
    "docker-compose.yml": ("Docker Compose", None),
    "docker-compose.yaml": ("Docker Compose", None),
    "compose.yml": ("Docker Compose", None),
    "compose.yaml": ("Docker Compose", None),
}

LOCKFILE_MANAGERS: dict[str, str] = {
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lockb": "bun",
    "poetry.lock": "poetry",
    "uv.lock": "uv",
    "pdm.lock": "pdm",
    "pipfile.lock": "pipenv",
    "cargo.lock": "cargo",
    "composer.lock": "composer",
    "gemfile.lock": "bundler",
    "go.sum": "go",
}

CI_MARKERS: tuple[tuple[str, str], ...] = (
    (".github/workflows", "GitHub Actions"),
    (".gitlab-ci.yml", "GitLab CI"),
    (".circleci/config.yml", "CircleCI"),
    ("jenkinsfile", "Jenkins"),
    ("azure-pipelines.yml", "Azure Pipelines"),
    (".travis.yml", "Travis CI"),
    ("bitbucket-pipelines.yml", "Bitbucket Pipelines"),
    (".drone.yml", "Drone CI"),
    ("buildkite", "Buildkite"),
    (".teamcity", "TeamCity"),
)

PEP517_BACKENDS: dict[str, str] = {
    "hatchling": "Hatch",
    "setuptools": "setuptools",
    "poetry.core": "Poetry",
    "flit_core": "Flit",
    "pdm.backend": "PDM",
    "maturin": "maturin",
    "scikit_build_core": "scikit-build",
}


def _read_toml(source: SourceFile) -> dict | None:
    if not source.text:
        return None
    try:
        return tomllib.loads(source.text)
    except (tomllib.TOMLDecodeError, ValueError):
        return None


def _read_json(source: SourceFile) -> dict | None:
    if not source.text:
        return None
    try:
        parsed = json.loads(source.text)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def analyse(files: list[SourceFile]) -> BuildInfo:
    info = BuildInfo()
    tools: set[str] = set()
    managers: set[str] = set()
    ci: set[str] = set()
    workspaces: list[str] = []

    by_relpath = {source.posix_relpath: source for source in files}

    for source in files:
        rel = source.posix_relpath
        name = source.name.lower()
        depth = rel.count("/")

        if name in LOCKFILE_MANAGERS:
            managers.add(LOCKFILE_MANAGERS[name])

        marker = MARKERS.get(name)
        if marker:
            # Only treat deeply-nested manifests as sub-projects, not as the
            # repo's own build system.
            if depth <= 2:
                tool, manager = marker
                tools.add(tool)
                if manager:
                    managers.add(manager)
                info.manifests.append(rel)
                info.evidence.append(Evidence(f"Found {source.name}", rel))
            elif name in {"package.json", "pom.xml", "pyproject.toml", "go.mod", "cargo.toml"}:
                workspaces.append(rel)

        if name in {"dockerfile", "containerfile"} or name.startswith("dockerfile."):
            info.containerised = True

        lowered_rel = rel.lower()
        for fragment, system in CI_MARKERS:
            if lowered_rel.startswith(fragment) or lowered_rel == fragment or fragment in lowered_rel:
                ci.add(system)

    # --- refine using manifest contents ---------------------------------
    pyproject = by_relpath.get("pyproject.toml")
    if pyproject:
        data = _read_toml(pyproject) or {}
        backend = (data.get("build-system") or {}).get("build-backend", "")
        for fragment, label in PEP517_BACKENDS.items():
            if fragment in str(backend):
                info.backend = label
                tools.discard("Python packaging")
                tools.add(label)
                break
        if "poetry" in str(data.get("tool", {}).keys()):
            managers.add("poetry")
        if "uv" in data.get("tool", {}):
            managers.add("uv")

    package_json = by_relpath.get("package.json")
    if package_json:
        data = _read_json(package_json) or {}
        declared_workspaces = data.get("workspaces")
        if isinstance(declared_workspaces, dict):
            declared_workspaces = declared_workspaces.get("packages", [])
        if isinstance(declared_workspaces, list) and declared_workspaces:
            workspaces.extend(str(item) for item in declared_workspaces)
        manager_field = data.get("packageManager")
        if isinstance(manager_field, str) and manager_field:
            managers.add(manager_field.split("@", 1)[0])
        for script_tool in ("vite", "webpack", "rollup", "esbuild", "parcel", "tsc", "turbo"):
            dev_deps = {**data.get("devDependencies", {}), **data.get("dependencies", {})}
            if script_tool in dev_deps:
                tools.add(script_tool)

    if "pnpm-workspace.yaml" in by_relpath:
        managers.add("pnpm")
        workspaces.append("pnpm-workspace.yaml")

    cargo = by_relpath.get("Cargo.toml") or by_relpath.get("cargo.toml")
    if cargo:
        data = _read_toml(cargo) or {}
        members = (data.get("workspace") or {}).get("members")
        if isinstance(members, list):
            workspaces.extend(str(member) for member in members)

    root_pom = by_relpath.get("pom.xml")
    if root_pom and root_pom.text:
        modules = re.findall(r"<module>\s*([^<]+?)\s*</module>", root_pom.text)
        workspaces.extend(modules)

    # --- project model ---------------------------------------------------
    nested_manifests = [
        source.posix_relpath
        for source in files
        if source.name.lower() in {"package.json", "pom.xml", "pyproject.toml", "go.mod",
                                   "cargo.toml", "build.gradle", "build.gradle.kts"}
        and source.posix_relpath.count("/") >= 1
    ]

    unique_workspaces = sorted({w for w in workspaces if w})
    info.workspaces = unique_workspaces

    if unique_workspaces:
        info.model = f"monorepo / multi-module ({len(unique_workspaces)} declared members)"
    elif len(nested_manifests) >= 3:
        info.model = f"multi-project layout ({len(nested_manifests)} nested manifests)"
    elif tools:
        info.model = "single project"
    else:
        info.model = "no build system detected"

    if info.containerised:
        info.model += ", containerised"

    info.tools = sorted(tools)
    info.package_managers = sorted(managers)
    info.ci_systems = sorted(ci)
    return info
