"""Self-contained HTML rendering — used by ``repostats scan`` for the consolidated report.

Every page embeds its own CSS, so the output tree can be opened straight from
disk (or served statically) with no build step and no external assets.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape as esc

from trinkets.repostats.models import Confidence, RepoReport

# A file-path -> URL callback. Returns None when no source page exists for
# that path (e.g. the file was too large, unreadable, or never referenced).
FileLinker = Callable[[str], "str | None"]

PALETTE = [
    "#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4",
    "#a855f7", "#ef4444", "#14b8a6", "#84cc16", "#3b82f6",
]

CONFIDENCE_CLASS = {
    Confidence.MEASURED: "conf-measured",
    Confidence.HIGH: "conf-high",
    Confidence.MEDIUM: "conf-medium",
    Confidence.LOW: "conf-low",
}
CONFIDENCE_LABEL = {
    Confidence.MEASURED: "measured",
    Confidence.HIGH: "high confidence",
    Confidence.MEDIUM: "medium confidence — inferred",
    Confidence.LOW: "low confidence — treat as a hint",
}

BASE_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #0f1115; --panel: #171a21; --border: #2a2f3a; --text: #e5e7eb;
  --muted: #9aa3b2; --accent: #6366f1; --link: #7dd3fc; --code-bg: #11141a;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f8fafc; --panel: #ffffff; --border: #e2e8f0; --text: #0f172a;
    --muted: #64748b; --accent: #4f46e5; --link: #0369a1; --code-bg: #f1f5f9;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1.25rem 4rem; background: var(--bg); color: var(--text);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main { max-width: 980px; margin: 0 auto; }
h1 { font-size: 1.7rem; margin: 0 0 0.35rem; }
h2 {
  font-size: 1.25rem; margin: 2.2rem 0 0.8rem;
  padding-top: 0.6rem; border-top: 1px solid var(--border);
}
h3 { font-size: 1.02rem; margin: 1.4rem 0 0.6rem; color: var(--muted); }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
.path {
  color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85rem; word-break: break-all;
}
.crumbs { color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }
.crumbs a { margin-right: 0.15rem; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1rem; font-size: 0.92rem; }
th, td {
  border: 1px solid var(--border); padding: 0.4rem 0.65rem;
  text-align: left; vertical-align: top;
}
th { background: var(--panel); font-weight: 600; }
tr:nth-child(even) td { background: color-mix(in srgb, var(--panel) 55%, transparent); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88em; }
code { background: var(--code-bg); border-radius: 3px; padding: 0.05em 0.35em; }
a.filelink code { color: var(--link); }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 1rem 1.2rem; margin: 0.8rem 0;
}
.badge {
  display: inline-block; font-size: 0.72rem; padding: 0.12rem 0.55rem; border-radius: 999px;
  border: 1px solid var(--border); color: var(--muted);
}
.conf-measured { color: #22c55e; border-color: #22c55e55; }
.conf-high { color: #38bdf8; border-color: #38bdf855; }
.conf-medium { color: #f59e0b; border-color: #f59e0b55; }
.conf-low { color: #f87171; border-color: #f8717155; }
.chip {
  display: inline-block; background: var(--code-bg); border: 1px solid var(--border);
  border-radius: 6px; padding: 0.08rem 0.5rem; margin: 0.1rem 0.25rem 0.1rem 0;
  font-size: 0.85rem;
}
blockquote {
  margin: 0.6rem 0; padding: 0.4rem 0.9rem; border-left: 3px solid var(--accent);
  color: var(--muted); background: var(--panel); border-radius: 0 6px 6px 0;
}
.callout {
  padding: 0.6rem 0.9rem; border-radius: 8px; background: #f59e0b1a;
  border: 1px solid #f59e0b55; margin: 0.8rem 0;
}
.callout ul { margin: 0.3rem 0 0; padding-left: 1.2rem; }
details { margin: 0.6rem 0; }
summary { cursor: pointer; color: var(--muted); }
.bars { margin: 0.6rem 0 1rem; }
.bar-row {
  display: flex; align-items: center; gap: 0.6rem; margin: 0.25rem 0; font-size: 0.85rem;
}
.bar-label {
  width: 9rem; flex: none; color: var(--muted); text-align: right;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.bar-track {
  flex: 1; background: var(--code-bg); border-radius: 4px; overflow: hidden; height: 0.85rem;
}
.bar-fill { height: 100%; border-radius: 4px; }
.bar-value { flex: none; width: 4.5rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.stack {
  display: flex; height: 0.9rem; border-radius: 5px; overflow: hidden; margin: 0.5rem 0 0.9rem;
}
.legend {
  display: flex; flex-wrap: wrap; gap: 0.4rem 1rem; font-size: 0.82rem;
  color: var(--muted); margin-bottom: 0.8rem;
}
.legend .swatch {
  display: inline-block; width: 0.65em; height: 0.65em; border-radius: 2px;
  margin-right: 0.35em; vertical-align: middle;
}
footer { margin-top: 3rem; color: var(--muted); font-size: 0.82rem; }
"""

SOURCE_STYLE = """
.src {
  width: 100%; border-collapse: collapse;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem;
}
.src td { border: none; padding: 0 0.6rem; white-space: pre; }
.src tr:target, .src tr.hl { background: #f59e0b2a; }
.src td.ln { color: var(--muted); text-align: right; user-select: none; width: 1%; }
.src td.code { white-space: pre-wrap; word-break: break-word; }
"""


def _page(title: str, body: str, *, extra_style: str = "") -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{esc(title)}</title>\n"
        f"<style>{BASE_STYLE}{extra_style}</style>\n"
        "</head>\n<body>\n<main>\n" + body + "\n</main>\n</body>\n</html>\n"
    )


def _pct(part: float, whole: float) -> float:
    return (part / whole * 100) if whole else 0.0


def _humanise_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _badge(confidence: Confidence) -> str:
    cls = CONFIDENCE_CLASS.get(confidence, "conf-low")
    label = CONFIDENCE_LABEL.get(confidence, confidence.value)
    return f'<span class="badge {cls}">{esc(label)}</span>'


def _chips(values: list[str]) -> str:
    return "".join(f'<span class="chip">{esc(v)}</span>' for v in values)


def _code(text: str, href: str | None = None) -> str:
    inner = f"<code>{esc(text)}</code>"
    return f'<a class="filelink" href="{esc(href)}">{inner}</a>' if href else inner


def _bar_row(label: str, value: str, pct: float, color: str) -> str:
    pct = max(0.0, min(100.0, pct))
    fill = f'<div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div>'
    return (
        '<div class="bar-row">'
        f'<div class="bar-label" title="{esc(label)}">{esc(label)}</div>'
        f'<div class="bar-track">{fill}</div>'
        f'<div class="bar-value">{esc(value)}</div>'
        "</div>"
    )


def _table(
    headers: list[str], rows: list[list[str]], *, numeric_cols: set[int] = frozenset()
) -> str:
    head = "".join(
        f'<th class="num">{esc(h)}</th>' if i in numeric_cols else f"<th>{esc(h)}</th>"
        for i, h in enumerate(headers)
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            f'<td class="num">{cell}</td>' if i in numeric_cols else f"<td>{cell}</td>"
            for i, cell in enumerate(row)
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


# --- sections --------------------------------------------------------------


def _section_header(report: RepoReport) -> str:
    rows = [
        ["Generated", esc(report.generated_at)],
        ["Analyser", f"repostats {esc(report.analyser_version)}"],
    ]
    if report.branch:
        rows.append(["Branch", _code(report.branch)])
    if report.head_commit:
        rows.append(["HEAD", _code(report.head_commit[:12])])
    if report.remote:
        rows.append(["Remote", esc(report.remote)])
    meta = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)

    html = [
        f"<h1>Repository report: {esc(report.name)}</h1>",
        f'<div class="path">{esc(report.path)}</div>',
        f"<table><tbody>{meta}</tbody></table>",
    ]
    if report.warnings:
        items = "".join(f"<li>{esc(w)}</li>" for w in report.warnings[:8])
        html.append(f'<div class="callout"><strong>Caveats</strong><ul>{items}</ul></div>')
    return "\n".join(html)


def _section_languages(report: RepoReport) -> str:
    code_languages = [entry for entry in report.languages if entry.is_code]
    other_languages = [entry for entry in report.languages if not entry.is_code]
    html = ["<h2>1. Programming languages</h2>"]

    if not code_languages:
        html.append("<p>No recognised source code found.</p>")
        return "\n".join(html)

    total_code = sum(entry.code_lines for entry in code_languages) or 1
    ranked = code_languages[:15]

    stack = "".join(
        f'<div style="width:{_pct(e.code_lines, total_code):.2f}%;'
        f'background:{PALETTE[i % len(PALETTE)]}"></div>'
        for i, e in enumerate(ranked)
    )
    legend = "".join(
        f'<span><span class="swatch" style="background:{PALETTE[i % len(PALETTE)]}">'
        f"</span>{esc(e.language)}</span>"
        for i, e in enumerate(ranked)
    )
    html.append(f'<div class="stack">{stack}</div><div class="legend">{legend}</div>')

    rows = [
        [
            esc(e.language), f"{e.files:,}", f"{e.code_lines:,}",
            f"{_pct(e.code_lines, total_code):.1f}%", f"{e.comment_lines:,}", f"{e.blank_lines:,}",
        ]
        for e in ranked
    ]
    html.append(
        _table(
            ["Language", "Files", "Code lines", "Share", "Comments", "Blank"],
            rows, numeric_cols={1, 2, 3, 4, 5},
        )
    )
    primary = code_languages[0]
    html.append(
        f"<p><strong>Primary language:</strong> {esc(primary.language)} "
        f"({_pct(primary.code_lines, total_code):.1f}% of source lines).</p>"
    )
    if other_languages:
        summary = ", ".join(f"{esc(e.language)} ({e.files})" for e in other_languages[:8])
        html.append(f"<p><strong>Config / markup files:</strong> {summary}.</p>")
    return "\n".join(html)


def _section_build(report: RepoReport, file_href: FileLinker) -> str:
    build = report.build
    html = ["<h2>2. Build tooling and project model</h2>"]
    rows = [
        ["Build tools", esc(", ".join(build.tools) or "none detected")],
        ["Package managers", esc(", ".join(build.package_managers) or "none detected")],
        ["PEP 517 backend", esc(build.backend or "—")],
        ["Project model", esc(build.model or "unknown")],
        ["CI systems", esc(", ".join(build.ci_systems) or "none detected")],
        ["Containerised", "yes" if build.containerised else "no"],
    ]
    html.append(_table(["Aspect", "Finding"], rows))
    if build.manifests:
        links = " ".join(_code(m, file_href(m)) for m in build.manifests[:12])
        html.append(f"<p><strong>Manifests found:</strong> {links}</p>")
    if build.workspaces:
        shown = ", ".join(f"<code>{esc(w)}</code>" for w in build.workspaces[:12])
        more = f" (+{len(build.workspaces) - 12} more)" if len(build.workspaces) > 12 else ""
        html.append(f"<p><strong>Workspace members:</strong> {shown}{more}</p>")
    return "\n".join(html)


def _section_purpose(report: RepoReport) -> str:
    purpose = report.purpose
    html = [
        f"<h2>3. Purpose and overall logic {_badge(purpose.confidence)}</h2>",
        f"<p>{esc(purpose.summary)}</p>",
    ]
    if purpose.declared_description:
        html.append(
            f"<p><strong>Declared description:</strong> {esc(purpose.declared_description)}</p>"
        )
    if purpose.readme_excerpt and purpose.readme_excerpt != purpose.declared_description:
        html.append(
            "<p><strong>README says:</strong></p>"
            f"<blockquote>{esc(purpose.readme_excerpt)}</blockquote>"
        )
    if purpose.detected_kinds:
        html.append(
            f"<p><strong>Detected project kind(s):</strong> {_chips(purpose.detected_kinds)}</p>"
        )
    if purpose.frameworks:
        html.append(
            f"<p><strong>Frameworks / platforms:</strong> {_chips(purpose.frameworks)}</p>"
        )
    if purpose.domain_terms:
        html.append(
            f"<p><strong>Recurring domain terms:</strong> {_chips(purpose.domain_terms)}</p>"
        )
    if purpose.evidence:
        items = "".join(
            f"<li>{esc(item.detail)}"
            + (f" — <code>{esc(item.path)}</code>" if item.path else "")
            + "</li>"
            for item in purpose.evidence
        )
        html.append(f"<details><summary>Evidence</summary><ul>{items}</ul></details>")
    return "\n".join(html)


def _section_contributors(report: RepoReport) -> str:
    info = report.contributors
    html = ["<h2>4. Contributors and commit timeframe</h2>"]
    if not info.total_commits:
        html.append("<p>No commit history available.</p>")
        return "\n".join(html)

    span = "—"
    if info.first_commit and info.last_commit:
        span = f"{info.first_commit} → {info.last_commit}"
    rows = [
        ["Total commits (excl. merges)", f"{info.total_commits:,}"],
        ["Distinct authors", f"{info.total_authors:,}"],
        ["Active span", esc(span)],
        ["Days with commits", f"{info.active_days:,}"],
        ["Bus factor", f"{info.bus_factor:,}"],
    ]
    html.append(_table(["Metric", "Value"], rows))
    if info.bus_factor_note:
        html.append(f"<p><em>{esc(info.bus_factor_note)}</em></p>")

    html.append("<h3>Top contributors</h3>")
    crows = [
        [
            esc(p.name), f"{p.commits:,}", f"{_pct(p.commits, info.total_commits):.1f}%",
            f"{p.insertions:,}", f"{p.deletions:,}",
            esc(f"{p.first_commit or '?'} → {p.last_commit or '?'}"),
        ]
        for p in info.top_contributors[:10]
    ]
    html.append(
        _table(
            ["Author", "Commits", "Share", "Insertions", "Deletions", "Active"],
            crows, numeric_cols={1, 2, 3, 4},
        )
    )

    if info.commits_by_year:
        html.append("<h3>Commits by year</h3>")
        peak = max(info.commits_by_year.values()) or 1
        bars = "".join(
            _bar_row(year, f"{count:,}", _pct(count, peak), PALETTE[i % len(PALETTE)])
            for i, (year, count) in enumerate(info.commits_by_year.items())
        )
        html.append(f'<div class="bars">{bars}</div>')
    return "\n".join(html)


def _section_flow(report: RepoReport) -> str:
    flow = report.flow
    html = [f"<h2>5. Flow: entry to persistence {_badge(flow.confidence)}</h2>"]
    if flow.note:
        html.append(f"<blockquote>{esc(flow.note)}</blockquote>")
    if flow.mermaid:
        html.append(f'<pre class="mono">{esc(flow.mermaid)}</pre>')
    interesting = [node for node in flow.nodes if node.evidence]
    if interesting:
        items = []
        for node in interesting:
            label = esc(node.label.replace("<br/>", " "))
            sub = "".join(
                "<li>" + esc(item.detail)
                + (f" — <code>{esc(item.path)}</code>" if item.path else "")
                + "</li>"
                for item in node.evidence
            )
            items.append(f"<li><strong>{label}</strong><ul>{sub}</ul></li>")
        summary = "How each node was identified"
        html.append(f"<details><summary>{summary}</summary><ul>{''.join(items)}</ul></details>")
    return "\n".join(html)


def _section_dependencies(report: RepoReport, file_href: FileLinker) -> str:
    deps = report.dependencies
    html = ["<h2>6. External dependencies and infrastructure</h2>"]

    if deps.by_category:
        html.append("<h3>Systems this code talks to</h3>")
        rows = [[esc(cat.title()), _chips(systems)] for cat, systems in deps.by_category.items()]
        html.append(_table(["Category", "Systems"], rows))
    else:
        html.append("<p>No databases, caches, queues or external services detected.</p>")

    if deps.infrastructure:
        html.append("<h3>Infrastructure evidence</h3>")
        rows = [
            [
                esc(d.name), esc(d.category), esc(d.detail or "—"),
                _code(d.source, file_href(d.source)),
            ]
            for d in deps.infrastructure[:20]
        ]
        html.append(_table(["System", "Category", "Evidence", "Source"], rows))

    html.append(
        f"<p><strong>Declared dependencies:</strong> {deps.total_declared:,} "
        "across all manifests.</p>"
    )

    notable = [d for d in deps.declared if d.category != "other"]
    if notable:
        rows = [
            [
                _code(d.name), esc(d.version or "—"), esc(d.category), esc(d.detail or "—"),
                _code(d.source, file_href(d.source)),
            ]
            for d in sorted(notable, key=lambda d: (d.category, d.name))[:60]
        ]
        table = _table(["Package", "Version", "Category", "Implies", "Manifest"], rows)
        summary = "Classified declared dependencies"
        html.append(f"<details><summary>{summary}</summary>{table}</details>")
    return "\n".join(html)


def _section_code_stats(report: RepoReport, file_href: FileLinker) -> str:
    code = report.code
    html = ["<h2>7. Size and structure</h2>"]
    comment_ratio = _pct(code.comment_lines, code.code_lines + code.comment_lines)
    rows = [
        ["Files analysed", f"{code.analysed_files:,}"],
        ["Files skipped (binary, vendored, generated)", f"{code.skipped_files:,}"],
        ["Total lines", f"{code.total_lines:,}"],
        ["Code lines", f"{code.code_lines:,}"],
        ["Comment lines", f"{code.comment_lines:,}"],
        ["Blank lines", f"{code.blank_lines:,}"],
        ["Comment ratio", f"{comment_ratio:.1f}%"],
        ["Classes / types", f"{code.classes:,}"],
        ["Functions / methods", f"{code.functions:,}"],
        ["HTTP endpoints", f"{code.api_endpoints:,}"],
        ["Repository size (analysed)", esc(_humanise_bytes(code.bytes))],
    ]
    html.append(_table(["Metric", "Value"], rows))

    if code.endpoints:
        html.append("<h3>API endpoints</h3>")
        rows = []
        for e in code.endpoints[:40]:
            href = file_href(e.path)
            loc_href = f"{href}#L{e.line}" if href else None
            rows.append(
                [
                    f"<code>{esc(e.method)}</code>", _code(e.route),
                    _code(f"{e.path}:{e.line}", loc_href), esc(e.framework),
                ]
            )
        html.append(_table(["Method", "Route", "Location", "Detected as"], rows))
        if len(code.endpoints) > 40:
            html.append(f"<p><em>{len(code.endpoints) - 40} more not shown.</em></p>")

    if code.counts_by_language:
        html.append("<h3>Declarations by language</h3>")
        rows = [
            [esc(lang), f"{counts['classes']:,}", f"{counts['functions']:,}"]
            for lang, counts in sorted(
                code.counts_by_language.items(), key=lambda item: -item[1]["functions"]
            )
        ]
        html.append(_table(["Language", "Classes / types", "Functions"], rows, numeric_cols={1, 2}))

    if code.largest_files:
        html.append("<h3>Largest source files</h3>")
        peak = max(count for _, count in code.largest_files) or 1
        bars = "".join(
            _largest_file_row(path, count, peak, PALETTE[i % len(PALETTE)], file_href(path))
            for i, (path, count) in enumerate(code.largest_files)
        )
        html.append(f'<div class="bars">{bars}</div>')
    return "\n".join(html)


def _largest_file_row(path: str, count: int, peak: int, color: str, href: str | None) -> str:
    label = f'<a class="filelink" href="{esc(href)}">{esc(path)}</a>' if href else esc(path)
    pct = max(0.0, min(100.0, _pct(count, peak)))
    fill = f'<div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div>'
    return (
        '<div class="bar-row">'
        f'<div class="bar-label" title="{esc(path)}">{label}</div>'
        f'<div class="bar-track">{fill}</div>'
        f'<div class="bar-value">{count:,}</div>'
        "</div>"
    )


def _section_testing(report: RepoReport) -> str:
    testing = report.testing
    html = ["<h2>8. Testing and coverage</h2>"]
    if testing.coverage_percent is not None:
        coverage = f"{testing.coverage_percent:.1f}%"
    else:
        coverage = "not measured"
    coverage_tools = ", ".join(testing.coverage_tools_configured) or "none"
    rows = [
        ["Test frameworks", esc(", ".join(testing.frameworks) or "none detected")],
        ["Coverage tooling configured", esc(coverage_tools)],
        ["Test files", f"{testing.test_files:,}"],
        ["Source files (non-test)", f"{testing.source_files:,}"],
        ["Test-to-source file ratio", f"{testing.test_to_source_ratio:.2f}"],
        ["Test functions / cases", f"{testing.test_functions:,}"],
        ["Lines of test code", f"{testing.test_lines:,}"],
        ["Line coverage", esc(coverage)],
    ]
    html.append(_table(["Metric", "Value"], rows))
    if testing.coverage_source:
        html.append(f"<p>Coverage read from <code>{esc(testing.coverage_source)}</code>.</p>")
    if testing.note:
        html.append(f"<blockquote>{esc(testing.note)}</blockquote>")
    return "\n".join(html)


def render_repo_report(
    report: RepoReport, *, file_href: FileLinker | None = None, index_href: str = "../index.html"
) -> str:
    """Render one repository's report as a standalone HTML page.

    ``file_href(path)`` maps a repo-relative file path to the URL of its
    generated source page, or returns None if no such page was generated.
    """
    linker: FileLinker = file_href or (lambda _path: None)
    body = "\n".join(
        [
            f'<div class="crumbs"><a href="{esc(index_href)}">&larr; all repositories</a></div>',
            _section_header(report),
            _section_languages(report),
            _section_build(report, linker),
            _section_purpose(report),
            _section_contributors(report),
            _section_flow(report),
            _section_dependencies(report, linker),
            _section_code_stats(report, linker),
            _section_testing(report),
            "<footer>Sections 3 and 5 are inferred from naming conventions, package metadata and "
            "declared dependencies — check the evidence blocks before relying on them.</footer>",
        ]
    )
    return _page(f"{report.name} — repostats", body)


def render_source_file(
    relpath: str,
    text: str,
    *,
    repo_name: str,
    report_href: str,
    index_href: str,
    truncated: bool = False,
) -> str:
    lines = text.splitlines() or [""]
    rows = []
    for n, line in enumerate(lines, start=1):
        rows.append(f'<tr id="L{n}"><td class="ln">{n}</td><td class="code">{esc(line)}</td></tr>')
    note = ""
    if truncated:
        note = "<p><em>File truncated — showing the first lines only.</em></p>"
    body = (
        f'<div class="crumbs"><a href="{esc(index_href)}">&larr; all repositories</a>'
        f' &nbsp;/&nbsp; <a href="{esc(report_href)}">&larr; {esc(repo_name)} report</a></div>'
        f"<h1>{esc(relpath)}</h1>"
        f"{note}"
        f'<table class="src"><tbody>{"".join(rows)}</tbody></table>'
    )
    return _page(f"{relpath} — {repo_name}", body, extra_style=SOURCE_STYLE)


def render_index(
    root_name: str,
    generated_at: str,
    rows: list[dict],
    errors: list[tuple[str, str]],
) -> str:
    """``rows`` items: name, display_path, report_href, language, code_lines,
    files, contributors, commits, bus_factor, warnings (count)."""
    body_rows = []
    for r in rows:
        name_cell = f'<a href="{esc(r["report_href"])}"><strong>{esc(r["name"])}</strong></a>'
        if r["display_path"] and r["display_path"] != r["name"]:
            name_cell += f'<div class="path">{esc(r["display_path"])}</div>'
        warn = ""
        if r["warnings"]:
            warn = f' <span class="badge conf-low">{r["warnings"]} warning(s)</span>'
        body_rows.append(
            "<tr>"
            f"<td>{name_cell}{warn}</td>"
            f'<td>{esc(r["language"] or "—")}</td>'
            f'<td class="num">{r["code_lines"]:,}</td>'
            f'<td class="num">{r["files"]:,}</td>'
            f'<td class="num">{r["contributors"]:,}</td>'
            f'<td class="num">{r["commits"]:,}</td>'
            f'<td class="num">{r["bus_factor"]:,}</td>'
            "</tr>"
        )
    table = (
        "<table><thead><tr><th>Repository</th><th>Primary language</th>"
        '<th class="num">Code lines</th><th class="num">Files</th>'
        '<th class="num">Contributors</th><th class="num">Commits</th>'
        '<th class="num">Bus factor</th></tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )

    error_block = ""
    if errors:
        items = "".join(f"<li><code>{esc(path)}</code> — {esc(msg)}</li>" for path, msg in errors)
        error_block = (
            f'<div class="callout"><strong>Could not be analysed</strong><ul>{items}</ul></div>'
        )

    repo_word = "repository" if len(rows) == 1 else "repositories"
    body = (
        f"<h1>Repository scan: {esc(root_name)}</h1>"
        f'<p class="path">Generated {esc(generated_at)} &middot; {len(rows)} {repo_word}</p>'
        f"{table}{error_block}"
    )
    return _page(f"Repository scan: {root_name} — repostats", body)
