"""Extension -> language mapping and comment syntax, used for classification and LOC counting."""

from __future__ import annotations

# Extension (lowercase, with dot) -> language name.
EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "Python", ".pyi": "Python", ".pyx": "Cython",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala", ".groovy": "Groovy",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".m": "Objective-C",
    ".c": "C", ".h": "C/C++ Header", ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++",
    ".cs": "C#", ".fs": "F#", ".vb": "Visual Basic",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".hrl": "Erlang",
    ".clj": "Clojure", ".cljs": "ClojureScript", ".hs": "Haskell", ".ml": "OCaml",
    ".lua": "Lua", ".pl": "Perl", ".pm": "Perl", ".r": "R", ".jl": "Julia", ".dart": "Dart",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell", ".ps1": "PowerShell",
    ".sql": "SQL", ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".sass": "Sass", ".less": "Less", ".vue": "Vue", ".svelte": "Svelte",
    ".proto": "Protocol Buffers", ".graphql": "GraphQL", ".gql": "GraphQL",
    ".tf": "Terraform", ".hcl": "HCL", ".dockerfile": "Dockerfile",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".toml": "TOML", ".xml": "XML",
    ".ini": "INI", ".cfg": "INI", ".properties": "Properties",
    ".md": "Markdown", ".rst": "reStructuredText", ".txt": "Text", ".adoc": "AsciiDoc",
    ".ipynb": "Jupyter Notebook", ".tex": "TeX",
}

# Filenames with no useful extension.
FILENAME_LANGUAGE: dict[str, str] = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "gnumakefile": "Makefile",
    "rakefile": "Ruby",
    "gemfile": "Ruby",
    "vagrantfile": "Ruby",
    "jenkinsfile": "Groovy",
    "brewfile": "Ruby",
    "procfile": "Procfile",
    "cmakelists.txt": "CMake",
}

# Languages that are configuration/markup rather than program source. Counted
# separately so "this repo is 80% YAML" doesn't drown out the actual code.
NON_CODE_LANGUAGES: frozenset[str] = frozenset({
    "YAML", "JSON", "TOML", "XML", "INI", "Properties", "Markdown",
    "reStructuredText", "Text", "AsciiDoc", "TeX", "CSV",
    # Files we could not classify are excluded from source-code totals rather
    # than being allowed to dominate the language breakdown.
    "Unknown",
})

# language -> (line comment prefixes, (block start, block end) or None)
COMMENT_SYNTAX: dict[str, tuple[tuple[str, ...], tuple[str, str] | None]] = {
    "Python": (("#",), ('"""', '"""')),
    "Cython": (("#",), ('"""', '"""')),
    "Ruby": (("#",), ("=begin", "=end")),
    "Shell": (("#",), None),
    "PowerShell": (("#",), ("<#", "#>")),
    "YAML": (("#",), None),
    "TOML": (("#",), None),
    "INI": (("#", ";"), None),
    "Properties": (("#", "!"), None),
    "Makefile": (("#",), None),
    "CMake": (("#",), None),
    "Dockerfile": (("#",), None),
    "Terraform": (("#", "//"), ("/*", "*/")),
    "HCL": (("#", "//"), ("/*", "*/")),
    "R": (("#",), None),
    "Julia": (("#",), ("#=", "=#")),
    "Perl": (("#",), None),
    "Elixir": (("#",), None),
    "Erlang": (("%",), None),
    "SQL": (("--",), ("/*", "*/")),
    "Lua": (("--",), ("--[[", "]]")),
    "Haskell": (("--",), ("{-", "-}")),
    "Clojure": ((";",), None),
    "ClojureScript": ((";",), None),
    "HTML": ((), ("<!--", "-->")),
    "XML": ((), ("<!--", "-->")),
    "Vue": ((), ("<!--", "-->")),
    "Svelte": ((), ("<!--", "-->")),
    "CSS": ((), ("/*", "*/")),
    "SCSS": (("//",), ("/*", "*/")),
    "Sass": (("//",), ("/*", "*/")),
    "Less": (("//",), ("/*", "*/")),
}

# Everything C-like shares // and /* */.
_C_STYLE = (
    "JavaScript", "TypeScript", "Java", "Kotlin", "Scala", "Groovy", "Go", "Rust",
    "PHP", "Swift", "Objective-C", "C", "C++", "C/C++ Header", "C#", "F#", "Dart",
    "Protocol Buffers", "GraphQL", "JSON",
)
for _lang in _C_STYLE:
    COMMENT_SYNTAX.setdefault(_lang, (("//",), ("/*", "*/")))

# Shebang interpreter -> language, for extensionless executable scripts.
SHEBANG_LANGUAGE: dict[str, str] = {
    "python": "Python", "python3": "Python", "python2": "Python",
    "sh": "Shell", "bash": "Shell", "zsh": "Shell", "dash": "Shell",
    "node": "JavaScript", "deno": "TypeScript", "bun": "JavaScript",
    "ruby": "Ruby", "perl": "Perl", "php": "PHP", "lua": "Lua", "Rscript": "R",
}


def classify(path_name: str, first_line: str | None = None) -> str | None:
    """Return the language for a filename, or None if unrecognised."""
    lowered = path_name.lower()

    if lowered in FILENAME_LANGUAGE:
        return FILENAME_LANGUAGE[lowered]

    # Handles Dockerfile.prod, Makefile.inc, docker-compose style prefixes.
    stem = lowered.split(".", 1)[0]
    if stem in FILENAME_LANGUAGE and stem in {"dockerfile", "makefile"}:
        return FILENAME_LANGUAGE[stem]

    dot = lowered.rfind(".")
    if dot > 0:
        language = EXTENSION_LANGUAGE.get(lowered[dot:])
        if language:
            return language

    if first_line and first_line.startswith("#!"):
        # "#!/usr/bin/env python3" or "#!/bin/bash"
        tokens = first_line[2:].strip().replace("\\", "/").split()
        for token in tokens:
            interpreter = token.rsplit("/", 1)[-1]
            if interpreter in SHEBANG_LANGUAGE:
                return SHEBANG_LANGUAGE[interpreter]
            if interpreter == "env":
                continue
    return None


def is_code(language: str) -> bool:
    return language not in NON_CODE_LANGUAGES
