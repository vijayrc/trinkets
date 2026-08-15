"""Probes 1 and 7: language breakdown, size metrics, and API surface.

Python is parsed with :mod:`ast` for exact class/function counts.  Every other
language is counted with declaration regexes, which is close but not exact —
the report labels which languages got which treatment.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict

from trinkets.repostats import languages as lang_table
from trinkets.repostats.models import ApiEndpoint, CodeStats, LanguageStat
from trinkets.repostats.walker import SourceFile

# language -> (class regex, function regex)
DECLARATION_PATTERNS: dict[str, tuple[re.Pattern[str] | None, re.Pattern[str] | None]] = {
    "JavaScript": (
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+\w+", re.MULTILINE),
        re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*\w+"
            r"|^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"
            r"|^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?function",
            re.MULTILINE,
        ),
    ),
    "Java": (
        re.compile(r"^\s*(?:public|private|protected|\s)*(?:final\s+|abstract\s+|static\s+)*"
                   r"(?:class|interface|enum|record)\s+\w+", re.MULTILINE),
        re.compile(r"^\s*(?:public|private|protected)\s+(?:static\s+|final\s+|synchronized\s+|"
                   r"abstract\s+|native\s+|default\s+)*[\w<>\[\],.\s?]+\s+\w+\s*\([^;{]*\)\s*"
                   r"(?:throws\s[\w.,\s]+)?\{", re.MULTILINE),
    ),
    "Go": (
        re.compile(r"^\s*type\s+\w+\s+(?:struct|interface)\b", re.MULTILINE),
        re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?\w+", re.MULTILINE),
    ),
    "Rust": (
        re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+\w+", re.MULTILINE),
        re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+\w+", re.MULTILINE),
    ),
    "Ruby": (
        re.compile(r"^\s*(?:class|module)\s+\w+", re.MULTILINE),
        re.compile(r"^\s*def\s+\w+", re.MULTILINE),
    ),
    "PHP": (
        re.compile(r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+\w+", re.MULTILINE),
        re.compile(r"^\s*(?:public|private|protected|static|\s)*function\s+\w+", re.MULTILINE),
    ),
    "C#": (
        re.compile(r"^\s*(?:public|private|protected|internal|\s)*(?:sealed\s+|abstract\s+|"
                   r"static\s+|partial\s+)*(?:class|interface|struct|record|enum)\s+\w+",
                   re.MULTILINE),
        re.compile(r"^\s*(?:public|private|protected|internal)\s+(?:static\s+|async\s+|"
                   r"virtual\s+|override\s+|sealed\s+)*[\w<>\[\],.\s?]+\s+\w+\s*\([^;)]*\)\s*\{",
                   re.MULTILINE),
    ),
    "C++": (
        re.compile(r"^\s*(?:class|struct)\s+\w+", re.MULTILINE),
        re.compile(r"^[\w:<>&*\s]+\s+[\w:]+\s*\([^;)]*\)\s*(?:const\s*)?\{", re.MULTILINE),
    ),
    "C": (None, re.compile(r"^[\w\s*]+\s+\w+\s*\([^;)]*\)\s*\{", re.MULTILINE)),
    "Swift": (
        re.compile(r"^\s*(?:public\s+|private\s+|internal\s+|open\s+)?(?:final\s+)?"
                   r"(?:class|struct|enum|protocol|extension)\s+\w+", re.MULTILINE),
        re.compile(r"^\s*(?:public\s+|private\s+|internal\s+|open\s+)?(?:static\s+)?func\s+\w+",
                   re.MULTILINE),
    ),
    "Shell": (None, re.compile(r"^\s*(?:function\s+)?\w+\s*\(\s*\)\s*\{", re.MULTILINE)),
    "Elixir": (
        re.compile(r"^\s*defmodule\s+[\w.]+", re.MULTILINE),
        re.compile(r"^\s*def(?:p)?\s+\w+", re.MULTILINE),
    ),
}
DECLARATION_PATTERNS["TypeScript"] = DECLARATION_PATTERNS["JavaScript"]
DECLARATION_PATTERNS["Kotlin"] = (
    re.compile(r"^\s*(?:open\s+|data\s+|sealed\s+|abstract\s+)*(?:class|interface|object)\s+\w+",
               re.MULTILINE),
    re.compile(r"^\s*(?:public\s+|private\s+|internal\s+|protected\s+)?(?:suspend\s+)?fun\s+\w+",
               re.MULTILINE),
)
DECLARATION_PATTERNS["Scala"] = (
    re.compile(r"^\s*(?:case\s+)?(?:class|object|trait)\s+\w+", re.MULTILINE),
    re.compile(r"^\s*def\s+\w+", re.MULTILINE),
)

EXACT_LANGUAGES = frozenset({"Python"})

# --- API route detection -------------------------------------------------
HTTP_VERBS = ("get", "post", "put", "patch", "delete", "head", "options")

ROUTE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    # @app.get("/x") / @router.post("/x") — FastAPI, Flask 2.x, Sanic
    ("Python decorator", re.compile(
        r"@\w+\.(" + "|".join(HTTP_VERBS) + r")\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "python"),
    # @app.route("/x", methods=["POST"])
    ("Flask route", re.compile(
        r"@\w+\.route\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?"), "flask"),
    # Django urls.py
    ("Django URLconf", re.compile(r"\b(?:path|re_path|url)\(\s*[r]?[\"']([^\"']*)[\"']"), "django"),
    # Express / Koa / Fastify
    ("Express", re.compile(
        r"\b(?:app|router|server|api)\.(" + "|".join(HTTP_VERBS) + r")\(\s*[\"'`]([^\"'`]+)"),
        "express"),
    # Spring
    ("Spring", re.compile(
        r"@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?[\"']([^\"']*)[\"']"),
        "spring"),
    # Go: gin / echo / chi / gorilla
    ("Go router", re.compile(
        r"\b\w+\.(GET|POST|PUT|PATCH|DELETE|HandleFunc|Handle)\(\s*[\"`]([^\"`]+)"), "go"),
    # Rails routes.rb
    ("Rails routes", re.compile(
        r"^\s*(" + "|".join(HTTP_VERBS) + r")\s+[\"']([^\"']+)[\"']", re.MULTILINE), "rails"),
)


def _count_python(source: SourceFile) -> tuple[int, int]:
    """Exact class/function counts via AST, falling back to regex on syntax errors."""
    if not source.text:
        return 0, 0
    try:
        tree = ast.parse(source.text)
    except (SyntaxError, ValueError, RecursionError):
        classes = len(re.findall(r"^\s*class\s+\w+", source.text, re.MULTILINE))
        functions = len(re.findall(r"^\s*(?:async\s+)?def\s+\w+", source.text, re.MULTILINE))
        return classes, functions

    classes = functions = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes += 1
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions += 1
    return classes, functions


def _blank_comments(text: str, language: str | None) -> str:
    """Replace comment bodies with spaces, preserving offsets and line numbers.

    Without this, a commented-out or documented route (``# @app.get("/x")``)
    counts as a real endpoint. Offsets are preserved so reported line numbers
    still point at the right place in the original file.
    """
    if not language:
        return text
    line_prefixes, block = lang_table.COMMENT_SYNTAX.get(language, ((), None))
    if not line_prefixes and not block:
        return text

    out: list[str] = []
    in_block = False
    block_start, block_end = block if block else ("", "")

    for line in text.split("\n"):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if in_block:
            out.append(" " * len(line))
            if block_end and block_end in stripped:
                in_block = False
            continue

        if block_start and stripped.startswith(block_start):
            out.append(" " * len(line))
            rest = stripped[len(block_start):]
            if not (block_end and block_end in rest):
                in_block = True
            continue

        cut = None
        for prefix in line_prefixes:
            position = line.find(prefix, indent)
            # Only treat it as a comment if it is not inside an obvious string.
            if position != -1 and line.count('"', 0, position) % 2 == 0 \
                    and line.count("'", 0, position) % 2 == 0:
                cut = position if cut is None else min(cut, position)
        out.append(line if cut is None else line[:cut] + " " * (len(line) - cut))

    return "\n".join(out)


def _detect_endpoints(source: SourceFile) -> list[ApiEndpoint]:
    if not source.text or not source.is_code:
        return []

    language = source.language or ""
    text = _blank_comments(source.text, source.language)
    endpoints: list[ApiEndpoint] = []

    relevant: list[tuple[str, re.Pattern[str], str]] = []
    for name, pattern, dialect in ROUTE_PATTERNS:
        if dialect in {"python", "flask", "django"} and language != "Python":
            continue
        if dialect == "express" and language not in {"JavaScript", "TypeScript"}:
            continue
        if dialect == "spring" and language not in {"Java", "Kotlin", "Groovy"}:
            continue
        if dialect == "go" and language != "Go":
            continue
        if dialect == "rails" and language != "Ruby":
            continue
        relevant.append((name, pattern, dialect))

    for name, pattern, dialect in relevant:
        for match in pattern.finditer(text):
            groups = match.groups()
            if dialect == "flask":
                route = groups[0]
                methods = groups[1] if len(groups) > 1 and groups[1] else "GET"
                method = ",".join(
                    sorted({m.strip().strip("\"'").upper() for m in methods.split(",") if m.strip()})
                ) or "GET"
            elif dialect == "django":
                route, method = groups[0], "ANY"
            elif dialect == "spring":
                verb = groups[0]
                method = "ANY" if verb == "Request" else verb.upper()
                route = groups[1]
            else:
                method = groups[0].upper()
                route = groups[1]
                if method in {"HANDLEFUNC", "HANDLE"}:
                    method = "ANY"

            line_number = text.count("\n", 0, match.start()) + 1
            endpoints.append(
                ApiEndpoint(
                    method=method,
                    route=route,
                    path=source.posix_relpath,
                    line=line_number,
                    framework=name,
                )
            )
    return endpoints


def analyse(files: list[SourceFile], skipped: int) -> tuple[list[LanguageStat], CodeStats]:
    stats = CodeStats()
    stats.total_files = len(files) + skipped
    stats.analysed_files = len(files)
    stats.skipped_files = skipped

    by_language: dict[str, LanguageStat] = {}
    counts_by_language: dict[str, dict[str, int]] = defaultdict(lambda: {"classes": 0,
                                                                        "functions": 0})
    exact_used: set[str] = set()
    heuristic_used: set[str] = set()
    file_sizes: list[tuple[str, int]] = []
    endpoints: list[ApiEndpoint] = []

    for source in files:
        language = source.language or "Unknown"
        entry = by_language.get(language)
        if entry is None:
            entry = LanguageStat(language=language, is_code=lang_table.is_code(language))
            by_language[language] = entry

        entry.files += 1
        entry.total_lines += source.total_lines
        entry.code_lines += source.code_lines
        entry.comment_lines += source.comment_lines
        entry.blank_lines += source.blank_lines
        entry.bytes += source.size_bytes

        stats.total_lines += source.total_lines
        stats.code_lines += source.code_lines
        stats.comment_lines += source.comment_lines
        stats.blank_lines += source.blank_lines
        stats.bytes += source.size_bytes

        if source.is_code:
            file_sizes.append((source.posix_relpath, source.total_lines))

        if source.language in EXACT_LANGUAGES:
            classes, functions = _count_python(source)
            exact_used.add(source.language)
        elif source.language in DECLARATION_PATTERNS and source.text:
            class_pattern, function_pattern = DECLARATION_PATTERNS[source.language]
            classes = len(class_pattern.findall(source.text)) if class_pattern else 0
            functions = len(function_pattern.findall(source.text)) if function_pattern else 0
            heuristic_used.add(source.language)
        else:
            classes = functions = 0

        stats.classes += classes
        stats.functions += functions
        if classes or functions:
            counts_by_language[language]["classes"] += classes
            counts_by_language[language]["functions"] += functions

        endpoints.extend(_detect_endpoints(source))

    # De-duplicate endpoints that several patterns matched at the same spot.
    unique: dict[tuple[str, int], ApiEndpoint] = {}
    for endpoint in endpoints:
        unique.setdefault((endpoint.path, endpoint.line), endpoint)
    stats.endpoints = sorted(unique.values(), key=lambda e: (e.path, e.line))
    stats.api_endpoints = len(stats.endpoints)

    stats.counts_by_language = dict(counts_by_language)
    stats.exact_parse_languages = sorted(exact_used)
    stats.heuristic_parse_languages = sorted(heuristic_used)
    stats.largest_files = sorted(file_sizes, key=lambda item: item[1], reverse=True)[:10]

    ranked = sorted(
        by_language.values(),
        key=lambda entry: (entry.is_code, entry.code_lines, entry.files),
        reverse=True,
    )
    return ranked, stats
