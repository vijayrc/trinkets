"""Markdown rendering — the default human-facing report."""

from __future__ import annotations

from trinkets.repostats.models import Confidence, RepoReport

CONFIDENCE_BADGE = {
    Confidence.MEASURED: "measured",
    Confidence.HIGH: "high confidence",
    Confidence.MEDIUM: "medium confidence — inferred",
    Confidence.LOW: "low confidence — treat as a hint",
}


def _pct(part: int, whole: int) -> str:
    return f"{(part / whole * 100):.1f}%" if whole else "—"


def _humanise_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _badge(confidence: Confidence) -> str:
    return f"*({CONFIDENCE_BADGE.get(confidence, confidence.value)})*"


def _section_languages(report: RepoReport) -> list[str]:
    lines = ["## 1. Programming languages", ""]
    code_languages = [entry for entry in report.languages if entry.is_code]
    other_languages = [entry for entry in report.languages if not entry.is_code]

    if not code_languages:
        lines += ["No recognised source code found.", ""]
        return lines

    total_code = sum(entry.code_lines for entry in code_languages) or 1
    lines += [
        "| Language | Files | Code lines | Share | Comments | Blank |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for entry in code_languages[:15]:
        lines.append(
            f"| {entry.language} | {entry.files:,} | {entry.code_lines:,} | "
            f"{_pct(entry.code_lines, total_code)} | {entry.comment_lines:,} | "
            f"{entry.blank_lines:,} |"
        )
    lines.append("")
    primary = code_languages[0]
    lines.append(
        f"**Primary language:** {primary.language} "
        f"({_pct(primary.code_lines, total_code)} of source lines)."
    )

    if other_languages:
        summary = ", ".join(
            f"{entry.language} ({entry.files})" for entry in other_languages[:8]
        )
        lines += ["", f"**Config / markup files:** {summary}."]
    lines.append("")
    return lines


def _section_build(report: RepoReport) -> list[str]:
    build = report.build
    lines = ["## 2. Build tooling and project model", ""]

    rows = [
        ("Build tools", ", ".join(build.tools) or "none detected"),
        ("Package managers", ", ".join(build.package_managers) or "none detected"),
        ("PEP 517 backend", build.backend or "—"),
        ("Project model", build.model or "unknown"),
        ("CI systems", ", ".join(build.ci_systems) or "none detected"),
        ("Containerised", "yes" if build.containerised else "no"),
    ]
    lines += ["| Aspect | Finding |", "| --- | --- |"]
    lines += [f"| {label} | {value} |" for label, value in rows]
    lines.append("")

    if build.manifests:
        lines += ["**Manifests found:** " + ", ".join(f"`{m}`" for m in build.manifests[:12]), ""]
    if build.workspaces:
        shown = ", ".join(f"`{w}`" for w in build.workspaces[:12])
        more = f" (+{len(build.workspaces) - 12} more)" if len(build.workspaces) > 12 else ""
        lines += [f"**Workspace members:** {shown}{more}", ""]
    return lines


def _section_purpose(report: RepoReport) -> list[str]:
    purpose = report.purpose
    lines = [f"## 3. Purpose and overall logic {_badge(purpose.confidence)}", ""]
    lines += [purpose.summary, ""]

    if purpose.declared_description:
        lines += [f"**Declared description:** {purpose.declared_description}", ""]
    if purpose.readme_excerpt and purpose.readme_excerpt != purpose.declared_description:
        lines += ["**README says:**", "", f"> {purpose.readme_excerpt}", ""]
    if purpose.detected_kinds:
        lines += ["**Detected project kind(s):** " + ", ".join(purpose.detected_kinds), ""]
    if purpose.frameworks:
        lines += ["**Frameworks / platforms:** " + ", ".join(purpose.frameworks), ""]
    if purpose.domain_terms:
        lines += [
            "**Recurring domain terms in paths:** "
            + ", ".join(f"`{term}`" for term in purpose.domain_terms),
            "",
        ]
    if purpose.evidence:
        lines.append("<details><summary>Evidence</summary>")
        lines.append("")
        for item in purpose.evidence:
            location = f" — `{item.path}`" if item.path else ""
            lines.append(f"- {item.detail}{location}")
        lines += ["", "</details>", ""]
    return lines


def _section_contributors(report: RepoReport) -> list[str]:
    info = report.contributors
    lines = ["## 4. Contributors and commit timeframe", ""]

    if not info.total_commits:
        lines += ["No commit history available.", ""]
        return lines

    span = "—"
    if info.first_commit and info.last_commit:
        span = f"{info.first_commit} → {info.last_commit}"

    lines += [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Total commits (excl. merges) | {info.total_commits:,} |",
        f"| Distinct authors | {info.total_authors:,} |",
        f"| Active span | {span} |",
        f"| Days with commits | {info.active_days:,} |",
        f"| Bus factor | {info.bus_factor} |",
        "",
    ]
    if info.bus_factor_note:
        lines += [f"*{info.bus_factor_note}*", ""]

    lines += [
        "### Top contributors",
        "",
        "| Author | Commits | Share | Insertions | Deletions | Active |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for person in info.top_contributors[:10]:
        active = f"{person.first_commit or '?'} → {person.last_commit or '?'}"
        lines.append(
            f"| {person.name} | {person.commits:,} | "
            f"{_pct(person.commits, info.total_commits)} | {person.insertions:,} | "
            f"{person.deletions:,} | {active} |"
        )
    lines.append("")

    if info.commits_by_year:
        peak = max(info.commits_by_year.values()) or 1
        lines += ["### Commits by year", "", "```"]
        for year, count in info.commits_by_year.items():
            bar = "█" * max(1, round(count / peak * 40))
            lines.append(f"{year}  {bar} {count:,}")
        lines += ["```", ""]
    return lines


def _section_flow(report: RepoReport) -> list[str]:
    flow = report.flow
    lines = [f"## 5. Flow: entry to persistence {_badge(flow.confidence)}", ""]

    if flow.note:
        lines += [f"> {flow.note}", ""]

    if flow.mermaid:
        lines += ["```mermaid", flow.mermaid, "```", ""]

    interesting = [node for node in flow.nodes if node.evidence]
    if interesting:
        lines.append("<details><summary>How each node was identified</summary>")
        lines.append("")
        for node in interesting:
            label = node.label.replace("<br/>", " ")
            lines.append(f"- **{label}**")
            for item in node.evidence:
                location = f" — `{item.path}`" if item.path else ""
                lines.append(f"  - {item.detail}{location}")
        lines += ["", "</details>", ""]
    return lines


def _section_dependencies(report: RepoReport) -> list[str]:
    deps = report.dependencies
    lines = ["## 6. External dependencies and infrastructure", ""]

    if deps.by_category:
        lines += ["### Systems this code talks to", "", "| Category | Systems |", "| --- | --- |"]
        for category, systems in deps.by_category.items():
            lines.append(f"| {category.title()} | {', '.join(systems)} |")
        lines.append("")
    else:
        lines += ["No databases, caches, queues or external services detected.", ""]

    if deps.infrastructure:
        lines += ["### Infrastructure evidence", "", "| System | Category | Evidence | Source |",
                  "| --- | --- | --- | --- |"]
        for dep in deps.infrastructure[:20]:
            lines.append(
                f"| {dep.name} | {dep.category} | {dep.detail or '—'} | `{dep.source}` |"
            )
        lines.append("")

    lines += [f"**Declared dependencies:** {deps.total_declared:,} across all manifests.", ""]

    notable = [dep for dep in deps.declared if dep.category != "other"]
    if notable:
        lines.append("<details><summary>Classified declared dependencies</summary>")
        lines += ["", "| Package | Version | Category | Implies | Manifest |",
                  "| --- | --- | --- | --- | --- |"]
        for dep in sorted(notable, key=lambda d: (d.category, d.name))[:60]:
            lines.append(
                f"| `{dep.name}` | {dep.version or '—'} | {dep.category} | "
                f"{dep.detail or '—'} | `{dep.source}` |"
            )
        lines += ["", "</details>", ""]
    return lines


def _section_code_stats(report: RepoReport) -> list[str]:
    code = report.code
    lines = ["## 7. Size and structure", ""]

    lines += [
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Files analysed | {code.analysed_files:,} |",
        f"| Files skipped (binary, vendored, generated) | {code.skipped_files:,} |",
        f"| Total lines | {code.total_lines:,} |",
        f"| Code lines | {code.code_lines:,} |",
        f"| Comment lines | {code.comment_lines:,} |",
        f"| Blank lines | {code.blank_lines:,} |",
        f"| Comment ratio | {_pct(code.comment_lines, code.code_lines + code.comment_lines)} |",
        f"| Classes / types | {code.classes:,} |",
        f"| Functions / methods | {code.functions:,} |",
        f"| HTTP endpoints | {code.api_endpoints:,} |",
        f"| Repository size (analysed) | {_humanise_bytes(code.bytes)} |",
        "",
    ]

    if code.exact_parse_languages or code.heuristic_parse_languages:
        notes = []
        if code.exact_parse_languages:
            notes.append(
                f"exact AST parsing for {', '.join(code.exact_parse_languages)}"
            )
        if code.heuristic_parse_languages:
            notes.append(
                f"regex heuristics for {', '.join(code.heuristic_parse_languages)} "
                "(counts are approximate)"
            )
        lines += [f"> Class/function counts use {'; '.join(notes)}.", ""]

    if code.endpoints:
        lines += ["### API endpoints", "", "| Method | Route | Location | Detected as |",
                  "| --- | --- | --- | --- |"]
        for endpoint in code.endpoints[:40]:
            lines.append(
                f"| `{endpoint.method}` | `{endpoint.route}` | "
                f"`{endpoint.path}:{endpoint.line}` | {endpoint.framework} |"
            )
        if len(code.endpoints) > 40:
            lines.append(f"| … | *{len(code.endpoints) - 40} more* | | |")
        lines.append("")

    if code.counts_by_language:
        lines += ["### Declarations by language", "",
                  "| Language | Classes / types | Functions |", "| --- | ---: | ---: |"]
        for language, counts in sorted(
            code.counts_by_language.items(), key=lambda item: -item[1]["functions"]
        ):
            lines.append(f"| {language} | {counts['classes']:,} | {counts['functions']:,} |")
        lines.append("")

    if code.largest_files:
        lines += ["### Largest source files", "", "| File | Lines |", "| --- | ---: |"]
        for path, count in code.largest_files:
            lines.append(f"| `{path}` | {count:,} |")
        lines.append("")
    return lines


def _section_testing(report: RepoReport) -> list[str]:
    testing = report.testing
    lines = ["## 8. Testing and coverage", ""]

    coverage = (
        f"{testing.coverage_percent:.1f}%" if testing.coverage_percent is not None else "not measured"
    )
    lines += [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Test frameworks | {', '.join(testing.frameworks) or 'none detected'} |",
        f"| Coverage tooling configured | {', '.join(testing.coverage_tools_configured) or 'none'} |",
        f"| Test files | {testing.test_files:,} |",
        f"| Source files (non-test) | {testing.source_files:,} |",
        f"| Test-to-source file ratio | {testing.test_to_source_ratio:.2f} |",
        f"| Test functions / cases | {testing.test_functions:,} |",
        f"| Lines of test code | {testing.test_lines:,} |",
        f"| Line coverage | {coverage} |",
        "",
    ]
    if testing.coverage_source:
        lines += [f"Coverage read from `{testing.coverage_source}`.", ""]
    if testing.note:
        lines += [f"> {testing.note}", ""]
    return lines


def _header(report: RepoReport) -> list[str]:
    lines = [
        f"# Repository report: {report.name}",
        "",
        f"`{report.path}`",
        "",
        "| | |",
        "| --- | --- |",
        f"| Generated | {report.generated_at} |",
        f"| Analyser | repostats {report.analyser_version} |",
    ]
    if report.branch:
        lines.append(f"| Branch | `{report.branch}` |")
    if report.head_commit:
        lines.append(f"| HEAD | `{report.head_commit[:12]}` |")
    if report.remote:
        lines.append(f"| Remote | {report.remote} |")
    lines.append("")

    if report.warnings:
        lines.append("> **Caveats**")
        for warning in report.warnings[:8]:
            lines.append(f"> - {warning}")
        lines.append("")
    return lines


def render_markdown(report: RepoReport) -> str:
    sections = [
        _header(report),
        _section_languages(report),
        _section_build(report),
        _section_purpose(report),
        _section_contributors(report),
        _section_flow(report),
        _section_dependencies(report),
        _section_code_stats(report),
        _section_testing(report),
        [
            "---",
            "",
            "*Sections 3 and 5 are inferred from naming conventions, package metadata and "
            "declared dependencies. They describe the architecture the layout implies, which "
            "is not always the architecture the code actually implements — check the evidence "
            "blocks before relying on them.*",
            "",
        ],
    ]
    return "\n".join(line for section in sections for line in section).rstrip() + "\n"
