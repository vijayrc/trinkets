"""Probe 5: request/data flow as a Mermaid diagram.

There is no reliable way to recover true call graphs across every language, so
this builds a *layer* diagram instead: it classifies files into architectural
roles using path and filename conventions, corroborates the endpoints of the
flow (entry points, datastores) with hard evidence from other probes, and wires
the layers together in their conventional order.

The result is an informed sketch of the intended architecture, not a verified
call graph — the report says so, and every node carries its evidence.
"""

from __future__ import annotations

import re

from trinkets.repostats.models import (
    ApiEndpoint,
    Confidence,
    DependencyInfo,
    Evidence,
    FlowEdge,
    FlowInfo,
    FlowNode,
)
from trinkets.repostats.walker import SourceFile

# layer key -> (display label, path/name fragments that imply the layer)
LAYER_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("middleware", "Middleware / filters",
     ("middleware", "middlewares", "interceptor", "interceptors", "filter", "filters", "guard")),
    ("controller", "Controllers / routes",
     ("controller", "controllers", "route", "routes", "router", "handler", "handlers",
      "endpoint", "endpoints", "resource", "resources", "view", "views", "api")),
    ("service", "Services / domain logic",
     ("service", "services", "usecase", "usecases", "use_case", "domain", "business",
      "manager", "managers", "core", "logic", "processor", "processors")),
    ("repository", "Repositories / data access",
     ("repository", "repositories", "repo", "dao", "daos", "store", "stores", "persistence",
      "mapper", "mappers", "query", "queries", "gateway")),
    ("model", "Models / entities",
     ("model", "models", "entity", "entities", "schema", "schemas", "dto", "domain_model")),
    ("worker", "Workers / consumers",
     ("worker", "workers", "consumer", "consumers", "task", "tasks", "job", "jobs",
      "scheduler", "cron", "listener", "listeners")),
    ("client", "External clients / adapters",
     ("client", "clients", "adapter", "adapters", "integration", "integrations",
      "connector", "connectors", "provider", "providers")),
)

ENTRYPOINT_FILENAMES: frozenset[str] = frozenset({
    "main.py", "__main__.py", "app.py", "application.py", "server.py", "wsgi.py", "asgi.py",
    "manage.py", "cli.py", "run.py", "entrypoint.py",
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "server.ts", "app.js", "app.ts",
    "main.go", "main.rs", "main.java", "application.java", "program.cs", "main.kt",
})

ENTRYPOINT_PATH_HINTS: tuple[str, ...] = ("cmd/", "bin/", "src/bin/")

MAIN_GUARD = re.compile(
    r"if\s+__name__\s*==\s*[\"']__main__[\"']"
    r"|func\s+main\s*\(\s*\)"
    r"|public\s+static\s+void\s+main\s*\("
    r"|fn\s+main\s*\(\s*\)",
)

# Categories that terminate a request, in the order they should appear.
SINK_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("database", "db", "cylinder"),
    ("cache", "cache", "cylinder"),
    ("messaging", "queue", "queue"),
    ("task queue", "queue", "queue"),
    ("search", "search", "cylinder"),
    ("cloud", "cloud", "rect"),
)

MAX_EVIDENCE_PER_NODE = 3


def _sanitise(text: str) -> str:
    """Make a string safe to embed in a Mermaid node label."""
    cleaned = text.replace('"', "'").replace("[", "(").replace("]", ")")
    cleaned = cleaned.replace("{", "(").replace("}", ")").replace("|", "/")
    return cleaned.strip()


def _classify_layers(files: list[SourceFile]) -> dict[str, list[str]]:
    """Map layer key -> example file paths."""
    found: dict[str, list[str]] = {}
    for source in files:
        if not source.is_code:
            continue
        rel = source.posix_relpath.lower()
        parts = rel.split("/")
        stem = parts[-1].rsplit(".", 1)[0]
        # Split identifiers so userService.ts and user_service.py both match.
        tokens = set()
        for part in parts[:-1]:
            tokens.update(re.split(r"[-_.]+", part))
        tokens.update(re.split(r"[-_.]+|(?<=[a-z])(?=[A-Z])", stem.lower()))

        for key, _label, fragments in LAYER_RULES:
            if tokens & set(fragments):
                found.setdefault(key, []).append(source.posix_relpath)
                break
    return found


def _find_entrypoints(files: list[SourceFile]) -> list[str]:
    entries: list[tuple[int, str]] = []
    for source in files:
        if not source.is_code:
            continue
        rel = source.posix_relpath
        lowered = rel.lower()
        name = source.name.lower()
        depth = rel.count("/")

        score = 0
        if name in ENTRYPOINT_FILENAMES:
            score += 10
        if any(hint in lowered for hint in ENTRYPOINT_PATH_HINTS):
            score += 6
        if source.text and MAIN_GUARD.search(source.text):
            score += 8
        if score:
            score -= depth  # prefer shallower files
            entries.append((score, rel))

    entries.sort(key=lambda item: (-item[0], item[1]))
    return [rel for _score, rel in entries[:4]]


def _node_id(prefix: str, index: int = 0) -> str:
    return f"{prefix}{index}" if index else prefix


def analyse(
    files: list[SourceFile],
    endpoints: list[ApiEndpoint],
    dependencies: DependencyInfo,
    frameworks: list[str],
) -> FlowInfo:
    info = FlowInfo()
    layers = _classify_layers(files)
    entrypoints = _find_entrypoints(files)

    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []
    signals = 0

    # --- 1. inbound edge -------------------------------------------------
    if endpoints:
        caller_label = "HTTP client"
        caller_detail = f"{len(endpoints)} route(s) declared"
    elif "CLI" in " ".join(frameworks) or any("cli" in path.lower() for path in entrypoints):
        caller_label = "User (CLI)"
        caller_detail = "command line invocation"
    else:
        caller_label = "Caller"
        caller_detail = "entry into the program"
    nodes.append(
        FlowNode("caller", caller_label, "external", "stadium",
                 [Evidence(caller_detail)])
    )

    # --- 2. entry points -------------------------------------------------
    if entrypoints:
        signals += 1
        label = "Entry point<br/>" + "<br/>".join(_sanitise(path) for path in entrypoints[:2])
        nodes.append(
            FlowNode("entry", label, "entry", "rect",
                     [Evidence("Entry point", path) for path in entrypoints[:MAX_EVIDENCE_PER_NODE]])
        )
        edges.append(FlowEdge("caller", "entry"))
        upstream = "entry"
    else:
        upstream = "caller"

    # --- 3. request-path layers -----------------------------------------
    for key, label, _fragments in LAYER_RULES:
        if key in {"worker", "client", "model"}:
            continue  # wired separately below
        paths = layers.get(key)
        if not paths:
            continue
        signals += 1
        node_label = f"{label}<br/>({len(paths)} file(s))"
        nodes.append(
            FlowNode(key, node_label, key, "rect",
                     [Evidence("Matched by path convention", path)
                      for path in sorted(paths)[:MAX_EVIDENCE_PER_NODE]])
        )
        edges.append(FlowEdge(upstream, key))
        upstream = key

    # If routes exist but no controller directory matched, add a synthetic
    # handler node so the diagram doesn't skip straight from entry to storage.
    if endpoints and "controller" not in layers:
        signals += 1
        by_file: dict[str, int] = {}
        for endpoint in endpoints:
            by_file[endpoint.path] = by_file.get(endpoint.path, 0) + 1
        top = sorted(by_file.items(), key=lambda item: -item[1])[:MAX_EVIDENCE_PER_NODE]
        nodes.append(
            FlowNode("handlers", f"Route handlers<br/>({len(endpoints)} endpoints)", "controller",
                     "rect",
                     [Evidence(f"{count} route(s)", path) for path, count in top])
        )
        edges.append(FlowEdge(upstream, "handlers"))
        upstream = "handlers"

    # Models sit beside the data-access layer rather than in the chain.
    if "model" in layers:
        paths = layers["model"]
        nodes.append(
            FlowNode("model", f"Models / entities<br/>({len(paths)} file(s))", "model", "rect",
                     [Evidence("Matched by path convention", path)
                      for path in sorted(paths)[:MAX_EVIDENCE_PER_NODE]])
        )
        anchor = "repository" if "repository" in layers else upstream
        edges.append(FlowEdge(anchor, "model", "maps to"))

    # --- 4. persistence and infrastructure sinks -------------------------
    sink_index = 0
    persisted = False
    for category, prefix, shape in SINK_CATEGORIES:
        systems = dependencies.by_category.get(category)
        if not systems:
            continue
        for system in systems[:4]:
            sink_index += 1
            node_id = _node_id(prefix, sink_index)
            evidence = [
                Evidence(f"Declared dependency implying {system}", dep.source)
                for dep in (*dependencies.declared, *dependencies.infrastructure)
                if dep.detail == system or dep.name == system
            ][:MAX_EVIDENCE_PER_NODE]
            nodes.append(FlowNode(node_id, _sanitise(system), category, shape, evidence))
            edges.append(FlowEdge(upstream, node_id, category))
            signals += 1
            if category == "database":
                persisted = True

    # --- 5. side channels ------------------------------------------------
    if "worker" in layers:
        paths = layers["worker"]
        nodes.append(
            FlowNode("worker", f"Workers / consumers<br/>({len(paths)} file(s))", "worker", "rect",
                     [Evidence("Matched by path convention", path)
                      for path in sorted(paths)[:MAX_EVIDENCE_PER_NODE]])
        )
        queue_node = next((node.node_id for node in nodes if node.layer in
                           {"messaging", "task queue"}), None)
        if queue_node:
            edges.append(FlowEdge(queue_node, "worker", "consumes"))
        else:
            edges.append(FlowEdge(upstream, "worker", "dispatches"))

    if "client" in layers or dependencies.by_category.get("http client"):
        detail_paths = layers.get("client", [])
        label = "External APIs"
        if detail_paths:
            label += f"<br/>({len(detail_paths)} adapter file(s))"
        nodes.append(
            FlowNode("external", label, "external-api", "stadium",
                     [Evidence("Adapter/client module", path)
                      for path in sorted(detail_paths)[:MAX_EVIDENCE_PER_NODE]])
        )
        edges.append(FlowEdge(upstream, "external", "calls out"))
        signals += 1

    # --- 6. response edge ------------------------------------------------
    if endpoints:
        edges.append(FlowEdge(upstream, "caller", "response"))

    # If we learned essentially nothing, say so rather than drawing a fiction.
    if signals <= 1 and not persisted:
        info.note = (
            "Not enough structural signal to infer a meaningful flow. The repository has no "
            "recognisable layer directories, HTTP routes, or datastore dependencies — it is "
            "most likely a library or a flat script collection."
        )
        info.confidence = Confidence.LOW
    else:
        info.confidence = Confidence.MEDIUM if signals >= 3 else Confidence.LOW
        info.note = (
            "Derived from directory/filename conventions plus declared dependencies. "
            "This is the intended architecture as the layout implies it, not a verified "
            "call graph."
        )

    info.nodes = nodes
    info.edges = edges
    info.mermaid = render_mermaid(nodes, edges)
    return info


SHAPE_WRAPPERS: dict[str, tuple[str, str]] = {
    "rect": ("[\"", "\"]"),
    "stadium": ("([\"", "\"])"),
    "cylinder": ("[(\"", "\")]"),
    "queue": (">\"", "\"]"),
    "diamond": ("{\"", "\"}"),
}

LAYER_STYLES: dict[str, str] = {
    "external": "fill:#eef2ff,stroke:#4f46e5,color:#1e1b4b",
    "external-api": "fill:#eef2ff,stroke:#4f46e5,color:#1e1b4b",
    "entry": "fill:#ecfdf5,stroke:#059669,color:#064e3b",
    "controller": "fill:#f0f9ff,stroke:#0284c7,color:#0c4a6e",
    "middleware": "fill:#f8fafc,stroke:#64748b,color:#0f172a",
    "service": "fill:#fefce8,stroke:#ca8a04,color:#422006",
    "repository": "fill:#fff7ed,stroke:#ea580c,color:#431407",
    "model": "fill:#fdf4ff,stroke:#a21caf,color:#4a044e",
    "worker": "fill:#f5f3ff,stroke:#7c3aed,color:#2e1065",
    "database": "fill:#fef2f2,stroke:#dc2626,color:#450a0a",
    "cache": "fill:#fff1f2,stroke:#e11d48,color:#4c0519",
    "messaging": "fill:#f0fdfa,stroke:#0d9488,color:#042f2e",
    "task queue": "fill:#f0fdfa,stroke:#0d9488,color:#042f2e",
    "search": "fill:#f7fee7,stroke:#65a30d,color:#1a2e05",
    "cloud": "fill:#f8fafc,stroke:#475569,color:#0f172a",
}


def render_mermaid(nodes: list[FlowNode], edges: list[FlowEdge]) -> str:
    lines = ["flowchart LR"]

    for node in nodes:
        open_wrap, close_wrap = SHAPE_WRAPPERS.get(node.shape, SHAPE_WRAPPERS["rect"])
        lines.append(f"    {node.node_id}{open_wrap}{_sanitise(node.label)}{close_wrap}")

    lines.append("")
    for edge in edges:
        if edge.label:
            lines.append(f"    {edge.source} -->|{_sanitise(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    styled = [node for node in nodes if node.layer in LAYER_STYLES]
    if styled:
        lines.append("")
        for node in styled:
            lines.append(f"    style {node.node_id} {LAYER_STYLES[node.layer]}")

    return "\n".join(lines)
