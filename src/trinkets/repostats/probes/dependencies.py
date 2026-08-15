"""Probe 6: external dependencies — databases, messaging, caches, and services.

Three independent evidence sources are merged:
  1. declared dependencies in package manifests,
  2. container images in Dockerfiles / compose files,
  3. import statements in source (catches transitive or undeclared usage).
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import defaultdict

from trinkets.repostats import knowledge
from trinkets.repostats.models import Confidence, Dependency, DependencyInfo
from trinkets.repostats.walker import SourceFile

try:  # optional; improves compose parsing
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised only without PyYAML
    yaml = None

_REQUIREMENT_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([<>=!~^].*)?$")
_PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_GRADLE_DEP = re.compile(
    r"""(?:implementation|api|compile|runtimeOnly|testImplementation|testCompile|
        compileOnly|annotationProcessor|kapt)\s*\(?\s*['"]([^'"]+)['"]""",
    re.VERBOSE,
)
_GO_REQUIRE = re.compile(r"^\s*([a-zA-Z0-9._~/-]+\.[a-z]{2,}/[^\s]+)\s+v[\d]", re.MULTILINE)
_DOCKER_FROM = re.compile(r"^\s*FROM\s+([^\s]+)", re.MULTILINE | re.IGNORECASE)
_COMPOSE_IMAGE = re.compile(r"^\s*image:\s*['\"]?([^'\"\s#]+)", re.MULTILINE)
_PY_IMPORT = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)", re.MULTILINE)
_JS_IMPORT = re.compile(r"""(?:from|require\()\s*['"]([^'"./][^'"]*)['"]""")
_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)", re.MULTILINE)


def _strip_pep508(spec: str) -> str | None:
    """'requests[socks] >=2,<3 ; python_version<"3.9"' -> 'requests'."""
    spec = spec.split(";", 1)[0].strip()
    if not spec or spec.startswith(("#", "-", ".", "/")):
        return None
    match = _PEP508_NAME.match(spec)
    return match.group(1) if match else None


def _from_pyproject(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    try:
        data = tomllib.loads(source.text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []

    found: list[tuple[str, str | None]] = []
    project = data.get("project", {})
    for spec in project.get("dependencies", []) or []:
        name = _strip_pep508(str(spec))
        if name:
            found.append((name, None))
    for extras in (project.get("optional-dependencies") or {}).values():
        for spec in extras or []:
            name = _strip_pep508(str(spec))
            if name:
                found.append((name, None))

    poetry = (data.get("tool") or {}).get("poetry") or {}
    for group in ("dependencies", "dev-dependencies"):
        for name, constraint in (poetry.get(group) or {}).items():
            if name.lower() != "python":
                version = constraint if isinstance(constraint, str) else None
                found.append((name, version))
    for group_data in (poetry.get("group") or {}).values():
        for name, constraint in (group_data.get("dependencies") or {}).items():
            if name.lower() != "python":
                found.append((name, constraint if isinstance(constraint, str) else None))
    return found


def _from_requirements(source: SourceFile) -> list[tuple[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    for line in source.lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-r", "--", "-e", "git+", "http")):
            continue
        name = _strip_pep508(stripped)
        if not name:
            continue
        match = _REQUIREMENT_LINE.match(stripped)
        version = match.group(3).strip() if match and match.group(3) else None
        found.append((name, version))
    return found


def _from_package_json(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    try:
        data = json.loads(source.text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    found: list[tuple[str, str | None]] = []
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        for name, version in (data.get(section) or {}).items():
            found.append((name, str(version) if version else None))
    return found


def _from_pom(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    found: list[tuple[str, str | None]] = []
    for block in re.findall(r"<dependency>(.*?)</dependency>", source.text, re.DOTALL):
        artifact = re.search(r"<artifactId>\s*([^<]+?)\s*</artifactId>", block)
        version = re.search(r"<version>\s*([^<]+?)\s*</version>", block)
        if artifact:
            found.append((artifact.group(1), version.group(1) if version else None))
    return found


def _from_gradle(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    found: list[tuple[str, str | None]] = []
    for coordinate in _GRADLE_DEP.findall(source.text):
        pieces = coordinate.split(":")
        if len(pieces) >= 2:
            found.append((pieces[1], pieces[2] if len(pieces) > 2 else None))
        else:
            found.append((coordinate, None))
    return found


def _from_go_mod(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    return [(module, None) for module in _GO_REQUIRE.findall(source.text)]


def _from_cargo(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    try:
        data = tomllib.loads(source.text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []
    found: list[tuple[str, str | None]] = []
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        for name, constraint in (data.get(section) or {}).items():
            version = constraint if isinstance(constraint, str) else None
            found.append((name, version))
    return found


def _from_gemfile(source: SourceFile) -> list[tuple[str, str | None]]:
    return [(name, None) for name in re.findall(r"^\s*gem\s+['\"]([^'\"]+)", source.text or "",
                                                re.MULTILINE)]


def _from_composer(source: SourceFile) -> list[tuple[str, str | None]]:
    if not source.text:
        return []
    try:
        data = json.loads(source.text)
    except (json.JSONDecodeError, ValueError):
        return []
    found: list[tuple[str, str | None]] = []
    for section in ("require", "require-dev"):
        for name, version in (data.get(section) or {}).items():
            if name.lower() not in {"php"}:
                found.append((name, str(version)))
    return found


PARSERS = {
    "pyproject.toml": _from_pyproject,
    "package.json": _from_package_json,
    "pom.xml": _from_pom,
    "build.gradle": _from_gradle,
    "build.gradle.kts": _from_gradle,
    "go.mod": _from_go_mod,
    "cargo.toml": _from_cargo,
    "gemfile": _from_gemfile,
    "composer.json": _from_composer,
}


def _compose_services(source: SourceFile) -> list[tuple[str, str]]:
    """Return (service name, image) pairs from a compose file."""
    if not source.text:
        return []
    if yaml is not None:
        try:
            data = yaml.safe_load(source.text)
            if isinstance(data, dict) and isinstance(data.get("services"), dict):
                pairs = []
                for name, spec in data["services"].items():
                    if isinstance(spec, dict) and spec.get("image"):
                        pairs.append((str(name), str(spec["image"])))
                return pairs
        except Exception:  # noqa: BLE001 - malformed YAML shouldn't kill the run
            pass
    return [("", image) for image in _COMPOSE_IMAGE.findall(source.text)]


def analyse(files: list[SourceFile]) -> DependencyInfo:
    info = DependencyInfo()
    seen_declared: set[tuple[str, str]] = set()
    seen_infra: set[str] = set()

    # --- 1. declared dependencies ---------------------------------------
    for source in files:
        name = source.name.lower()
        parser = PARSERS.get(name)
        if parser is None and (name.startswith("requirements") and name.endswith(".txt")):
            parser = _from_requirements
        if parser is None:
            continue

        for dep_name, version in parser(source):
            key = (knowledge.normalise(dep_name), source.posix_relpath)
            if key in seen_declared:
                continue
            seen_declared.add(key)

            classified = knowledge.classify_package(dep_name)
            category, detail = classified if classified else ("other", None)
            info.declared.append(
                Dependency(
                    name=dep_name,
                    category=category,
                    source=source.posix_relpath,
                    version=version,
                    detail=detail,
                    confidence=Confidence.HIGH,
                )
            )

    info.total_declared = len(info.declared)

    # --- 2. container images --------------------------------------------
    for source in files:
        name = source.name.lower()
        is_compose = name.startswith(("docker-compose", "compose")) and name.endswith(
            (".yml", ".yaml")
        )
        is_dockerfile = name == "dockerfile" or name.startswith("dockerfile.")

        images: list[tuple[str, str]] = []
        if is_compose:
            images = _compose_services(source)
        elif is_dockerfile and source.text:
            images = [("", image) for image in _DOCKER_FROM.findall(source.text)]

        for service_name, image in images:
            classified = knowledge.classify_image(image)
            if not classified:
                continue
            category, system = classified
            if system in seen_infra:
                continue
            seen_infra.add(system)
            label = f"{service_name} ({image})" if service_name else image
            info.infrastructure.append(
                Dependency(
                    name=system,
                    category=category,
                    source=source.posix_relpath,
                    detail=f"container image: {label}",
                    confidence=Confidence.HIGH,
                )
            )

    # --- 3. imports in source -------------------------------------------
    import_systems: dict[str, tuple[str, str]] = {}
    for source in files:
        if not source.text or not source.is_code:
            continue
        modules: list[str] = []
        if source.language in {"Python", "Cython"}:
            modules = _PY_IMPORT.findall(source.text)
        elif source.language in {"JavaScript", "TypeScript"}:
            modules = _JS_IMPORT.findall(source.text)
        elif source.language in {"Java", "Kotlin", "Scala"}:
            modules = _JAVA_IMPORT.findall(source.text)
        if not modules:
            continue

        for module in modules:
            root = module.split(".", 1)[0].lower()
            for fragment, category, system in knowledge.IMPORT_SYSTEMS:
                if fragment in root:
                    import_systems.setdefault(system, (category, source.posix_relpath))
                    break

    declared_systems = {dep.detail for dep in info.declared if dep.detail}
    infra_systems = {dep.name for dep in info.infrastructure}
    for system, (category, path) in sorted(import_systems.items()):
        if system in declared_systems or system in infra_systems:
            continue
        info.infrastructure.append(
            Dependency(
                name=system,
                category=category,
                source=path,
                detail="inferred from import statements (not found in any manifest)",
                confidence=Confidence.MEDIUM,
            )
        )

    # --- roll up ---------------------------------------------------------
    by_category: dict[str, set[str]] = defaultdict(set)
    for dep in info.declared:
        if dep.category != "other" and dep.detail:
            by_category[dep.category].add(dep.detail)
    for dep in info.infrastructure:
        by_category[dep.category].add(dep.name)

    info.by_category = {
        category: sorted(by_category[category])
        for category in knowledge.CATEGORY_ORDER
        if by_category.get(category)
    }
    return info
